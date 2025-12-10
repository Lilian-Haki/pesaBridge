import json
from decimal import Decimal, InvalidOperation
from app.mpesa.stk_push import lipa_na_mpesa_stk_push
from django.views.decorators.csrf import csrf_exempt
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db.models import Sum, DecimalField, F
from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login, get_user_model, update_session_auth_hash, logout
from .models import Notification, LenderWallet, Transaction, Loan, LoanApplication, LoanPayment
from django.contrib.auth.hashers import make_password
from django.http import HttpResponse
import csv
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import LoanApplicationForm
from django.http import JsonResponse

# Create your views here.
User = get_user_model()

def index(request):
    return render(request, 'index.html')
def login_user(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)

            # Redirect based on role
            if user.role == "borrower":
                return redirect("borrower")
            elif user.role == "lender":
                return redirect("lender")
            else:
                return redirect("admin")
        else:
            return render(request, "login.html", {"error": "Invalid credentials"})

    return render(request, "login.html")
def logout_user(request):
    logout(request)
    return redirect("login")
def register(request):
    if request.method == "POST":
        firstname = request.POST.get("firstname")
        lastname = request.POST.get("lastname")
        username = request.POST.get("username")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        password = request.POST.get("password")
        confirmpassword = request.POST.get("confirmPassword")
        role = request.POST.get("role", "borrower")    # Default: borrower

        # CHECK: Password match
        if password != confirmpassword:
            return render(request, "register.html", {
                "error": "Passwords do not match"
            })

        # CHECK: Username exists?
        if User.objects.filter(username=username).exists():
            return render(request, "register.html", {
                "error": "Username already taken."
            })

        # CHECK: Email exists?
        if User.objects.filter(email=email).exists():
            return render(request, "register.html", {
                "error": "Email already exists."
            })

        # CREATE USER
        user = User.objects.create(
            first_name=firstname,
            last_name=lastname,
            username=username,
            email=email,
            phone=phone,
            role=role,
            password=make_password(password)
        )

        messages.success(request, "Account created successfully! Please log in.")
        return redirect("login")

    return render(request, "register.html")
@login_required
def apply_loan(request):
    """
    Handles loan application form (apply_loan.html).
    On POST create LoanApplication; admin will approve and create Loan entity later.
    """
    if request.method == 'POST':
        form = LoanApplicationForm(request.POST)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            try:
                app.save()
                print("Saved LoanApplication with ID:", app.id)
            except Exception as e:
                print("Save failed:", e)
                messages.error(request, f"Database error: {e}")
                return render(request, 'borrower/apply_loan.html', {'form': form})
            messages.success(request, "Loan application submitted successfully!")
            return render(request,'borrower/apply_loan.html')
        else:
            print("Form errors:", form.errors)
            messages.error(request, "Please fix the errors below.")
            return render(request, 'borrower/apply_loan.html', {'form': form})
    else:
        form = LoanApplicationForm()
    return render(request, 'borrower/apply_loan.html', {'form': form})
@login_required
def my_loans(request):

    # Only final loans for the logged-in user
    loans = Loan.objects.filter(user=request.user).order_by('-created_at')

    total_borrowed = sum([l.amount for l in loans])
    active_loans_count = loans.filter(status='Active', closed=False).count()
    total_outstanding = sum([
        (l.amount + (l.amount * l.interest_rate / 100) - l.paid_amount)
        for l in loans if l.status == 'Active'
    ])

    # Attach calculated progress field from the model
    loans_with_progress = []
    for l in loans:
        loans_with_progress.append({
            'object': l,
            'progress': l.progress_percent    # from the @property in your model
        })

    context = {
        'loans': loans,
        'loans_with_progress': loans_with_progress,
        'total_borrowed': total_borrowed,
        'active_loans': active_loans_count,
        'total_outstanding': total_outstanding,
    }

    print("Loans:", loans)
    print("Total Borrowed:", total_borrowed)
    print("Active Loans:", active_loans_count)
    print("Total Outstanding:", total_outstanding)
    print("Logged in user ID:", request.user.id)

    return render(request, 'borrower/my_loans.html', context)
def format_phone_for_mpesa(phone):
    """
    Converts phone number to international format (2547xxxxxxx).
    Removes dots or spaces.
    """
    phone = phone.replace(".", "").replace(" ", "")
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    return phone
@login_required
def repay_loan(request):
    """
    Handle loan repayment via M-Pesa STK Push or Manual Payment
    """
    print("\n" + "=" * 70)
    print("REPAY LOAN VIEW CALLED")
    print("=" * 70)

    # Get all active loans for this borrower
    active_loans = Loan.objects.filter(
        user=request.user,
        status="Active",
        closed=False
    ).order_by('-funded_date')

    print(f"Active loans for user {request.user.username}: {active_loans.count()}")

    selected_loan_data = None

    if request.method == "POST":
        print("\n--- POST REQUEST ---")
        loan_id = request.POST.get("loan")
        amount = request.POST.get("amount")
        payment_method = request.POST.get("payment_method")  # NEW: Get payment method

        print(f"Loan ID: {loan_id}")
        print(f"Amount: {amount}")
        print(f"Payment Method: {payment_method}")

        # Validation
        if not loan_id or not amount:
            messages.error(request, "Please select a loan and enter an amount.")
            return redirect("repay_loan")

        if not payment_method:
            messages.error(request, "Please select a payment method.")
            return redirect("repay_loan")

        # Validate amount
        try:
            amount = Decimal(amount)
            if amount <= 0:
                messages.error(request, "Amount must be greater than zero.")
                return redirect("repay_loan")
            print(f"✓ Amount validated: {amount}")
        except (ValueError, InvalidOperation) as e:
            print(f"✗ Amount validation error: {e}")
            messages.error(request, "Invalid amount format.")
            return redirect("repay_loan")

        # Get the loan
        try:
            loan = Loan.objects.get(id=loan_id, user=request.user)
            print(f"✓ Loan found: #{loan.id}")
        except Loan.DoesNotExist:
            print(f"✗ Loan not found")
            messages.error(request, "Loan not found.")
            return redirect("repay_loan")

        # Check if loan is active
        if loan.status != "Active" or loan.closed:
            print(f"✗ Loan not active: status={loan.status}, closed={loan.closed}")
            messages.error(request, "This loan is not active.")
            return redirect("repay_loan")

        # Check if amount exceeds balance
        if amount > loan.balance:
            print(f"✗ Amount exceeds balance: {amount} > {loan.balance}")
            messages.error(request, f"Payment amount (${amount}) exceeds outstanding balance (${loan.balance}).")
            return redirect("repay_loan")

        # ===== PAYMENT METHOD HANDLING =====

        if payment_method == "manual":
            # MANUAL PAYMENT: Instant deduction
            print("\n--- MANUAL PAYMENT SELECTED ---")

            try:
                # Update loan
                old_paid = loan.paid_amount
                loan.paid_amount += amount
                new_paid = loan.paid_amount

                print(f"Old paid amount: ${old_paid}")
                print(f"Payment amount: ${amount}")
                print(f"New paid amount: ${new_paid}")
                print(f"Total due: ${loan.amount + loan.interest}")

                # Check if fully paid
                if loan.paid_amount >= (loan.amount + loan.interest):
                    loan.status = "Completed"
                    loan.closed = True
                    print(f"✓ Loan fully paid and closed")

                loan.save()

                # Create payment record
                payment = LoanPayment.objects.create(
                    loan=loan,
                    user=loan.user,
                    amount=amount,
                    payment_method="Manual"
                )
                print(f"✓ Payment record created: #{payment.id}")

                messages.success(
                    request,
                    f"Payment of ${amount} processed successfully! New balance: ${loan.balance}"
                )

                print("=" * 70 + "\n")
                return redirect("my_loans")

            except Exception as e:
                print(f"✗ Manual payment error: {e}")
                import traceback
                traceback.print_exc()
                messages.error(request, f"Payment processing failed: {str(e)}")
                return redirect("repay_loan")

        elif payment_method == "mpesa":
            # M-PESA PAYMENT: STK Push
            print("\n--- M-PESA PAYMENT SELECTED ---")

            # Format phone number for M-Pesa
            phone = request.user.phone
            print(f"Original phone: {phone}")

            if not phone:
                print(f"✗ No phone number in profile")
                messages.error(request, "Phone number not found in your profile. Please update your profile.")
                return redirect("bsettings")

            # Format to international format (254XXXXXXXXX)
            phone = str(phone).strip()
            phone = phone.replace(" ", "").replace("-", "").replace("+", "")

            if phone.startswith("0"):
                phone = "254" + phone[1:]
            elif phone.startswith("7") or phone.startswith("1"):
                phone = "254" + phone
            elif not phone.startswith("254"):
                print(f"✗ Invalid phone format: {phone}")
                messages.error(request, "Invalid phone number format. Please update your profile.")
                return redirect("bsettings")

            print(f"Formatted phone: {phone}")

            # Initiate M-Pesa STK Push
            print("\nInitiating STK Push...")
            try:
                response = lipa_na_mpesa_stk_push(
                    phone=phone,
                    amount=int(amount),
                    account_reference=f"Loan-{loan.id}",
                    description=f"Loan Repayment for Loan #{loan.id}",
                )

                print(f"\nSTK Push Response:")
                print(f"Type: {type(response)}")
                print(f"Content: {response}")

                # Check response
                if response and isinstance(response, dict):
                    response_code = response.get("ResponseCode")
                    print(f"Response Code: {response_code}")

                    if response_code == "0":
                        print("✓ STK Push successful!")
                        messages.success(
                            request,
                            "Payment request sent! Please check your phone and enter your M-Pesa PIN to complete the payment."
                        )
                    else:
                        error_message = response.get("errorMessage") or response.get(
                            "ResponseDescription") or "Unknown error"
                        print(f"✗ STK Push failed: {error_message}")
                        messages.error(request, f"Failed to initiate payment: {error_message}")
                else:
                    print(f"✗ Invalid response format: {response}")
                    messages.error(request, "Failed to initiate payment: Invalid response from M-Pesa")

            except Exception as e:
                print(f"✗ Exception during STK Push: {e}")
                import traceback
                traceback.print_exc()
                messages.error(request, f"Payment error: {str(e)}")

            print("=" * 70 + "\n")
            return redirect("repay_loan")

        else:
            messages.error(request, "Invalid payment method selected.")
            return redirect("repay_loan")

    # GET request - handle loan selection via query parameter
    loan_id = request.GET.get("loan")

    if loan_id:
        try:
            selected_loan_data = Loan.objects.get(id=loan_id, user=request.user)
            print(f"Selected loan: #{selected_loan_data.id}")
        except Loan.DoesNotExist:
            messages.warning(request, "Selected loan not found.")

    context = {
        "active_loans": active_loans,
        "selected_loan_data": selected_loan_data,
    }

    return render(request, "borrower/repay_loan.html", context)
@csrf_exempt
def mpesa_stk_callback(request):
    """
    Handle M-Pesa STK Push callback
    """
    print("\n" + "=" * 70)
    print("M-PESA CALLBACK RECEIVED")
    print("=" * 70)
    print(f"Method: {request.method}")
    print(f"Content-Type: {request.content_type}")

    # Handle GET requests (for testing)
    if request.method == "GET":
        return JsonResponse({
            "message": "M-Pesa callback endpoint is active",
            "status": "ready"
        })

    # Log raw body
    try:
        raw_body = request.body.decode('utf-8')
        print(f"Raw Body:\n{raw_body}")
    except Exception as e:
        print(f"Could not decode body: {e}")
        return JsonResponse({
            "ResultCode": 1,
            "ResultDesc": "Could not decode request body"
        }, status=400)

    # Parse JSON
    try:
        data = json.loads(raw_body)
        print(f"Parsed JSON:\n{json.dumps(data, indent=2)}")
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        print(f"Invalid JSON received")
        return JsonResponse({
            "ResultCode": 1,
            "ResultDesc": "Invalid JSON format"
        }, status=400)

    # Extract callback data
    try:
        body = data.get("Body", {})
        stk_callback = body.get("stkCallback", {})
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc", "No description")

        print(f"Result Code: {result_code}")
        print(f"Result Description: {result_desc}")

        # Payment failed
        if result_code != 0:
            print(f"✗ Payment failed or cancelled")
            return JsonResponse({
                "ResultCode": 0,
                "ResultDesc": "Callback acknowledged"
            })

        # Extract metadata
        callback_metadata = stk_callback.get("CallbackMetadata", {})
        items = callback_metadata.get("Item", [])

        if not items:
            print("✗ No callback items found")
            return JsonResponse({
                "ResultCode": 0,
                "ResultDesc": "No metadata"
            })

        # Parse items
        amount = None
        mpesa_receipt = None
        phone = None
        transaction_date = None

        for item in items:
            name = item.get("Name")
            value = item.get("Value")

            if name == "Amount":
                amount = Decimal(str(value))
            elif name == "MpesaReceiptNumber":
                mpesa_receipt = value
            elif name == "PhoneNumber":
                phone = str(value)
            elif name == "TransactionDate":
                transaction_date = value

        print(f"Amount: {amount}")
        print(f"Receipt: {mpesa_receipt}")
        print(f"Phone: {phone}")

        # Extract account reference
        account_ref = stk_callback.get("AccountReference", "")
        print(f"Account Reference: {account_ref}")

        if not account_ref or not account_ref.startswith("Loan-"):
            print(f"✗ Invalid account reference format")
            return JsonResponse({
                "ResultCode": 0,
                "ResultDesc": "Invalid reference format"
            })

        # Parse loan ID
        try:
            loan_id = int(account_ref.split("-")[1])
            print(f"Loan ID: {loan_id}")
        except (IndexError, ValueError) as e:
            print(f"✗ Could not parse loan ID: {e}")
            return JsonResponse({
                "ResultCode": 0,
                "ResultDesc": "Invalid loan ID"
            })

        # Get loan
        try:
            loan = Loan.objects.get(id=loan_id)
            print(f"✓ Loan found: #{loan.id}")
        except Loan.DoesNotExist:
            print(f"✗ Loan #{loan_id} not found in database")
            return JsonResponse({
                "ResultCode": 0,
                "ResultDesc": "Loan not found"
            })

        # Update loan
        old_paid = loan.paid_amount
        loan.paid_amount += amount
        new_paid = loan.paid_amount

        print(f"Old paid amount: ${old_paid}")
        print(f"Payment amount: ${amount}")
        print(f"New paid amount: ${new_paid}")
        print(f"Total due: ${loan.amount + loan.interest}")

        # Check if fully paid
        if loan.paid_amount >= (loan.amount + loan.interest):
            loan.status = "Completed"
            loan.closed = True
            print(f"✓ Loan fully paid and closed")

        loan.save()

        # Create payment record
        payment = LoanPayment.objects.create(
            loan=loan,
            user=loan.user,
            amount=amount,
            payment_method="M-Pesa"
        )
        print(f"✓ Payment record created: #{payment.id}")

        print(f"✓ Payment processed successfully!")
        print("=" * 70 + "\n")

        return JsonResponse({
            "ResultCode": 0,
            "ResultDesc": "Payment received and processed"
        })

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 70 + "\n")

        return JsonResponse({
            "ResultCode": 1,
            "ResultDesc": f"Processing error: {str(e)}"
        }, status=500)

@login_required
@csrf_exempt
def test_mpesa_callback(request):
    """
    Manual testing endpoint to simulate M-Pesa callback
    Use this to test your callback logic on localhost
    """
    if request.method == "GET":
        # Show a form to manually trigger callback
        return render(request, 'test_callback.html')

    if request.method == "POST":
        loan_id = request.POST.get("loan_id")
        amount = request.POST.get("amount")

        # Simulate successful callback data
        simulated_callback = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "test-merchant-123",
                    "CheckoutRequestID": "test-checkout-456",
                    "ResultCode": 0,
                    "ResultDesc": "The service request is processed successfully.",
                    "AccountReference": f"Loan-{loan_id}",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": float(amount)},
                            {"Name": "MpesaReceiptNumber", "Value": f"TEST{loan_id}"},
                            {"Name": "PhoneNumber", "Value": "254708374149"},
                            {"Name": "TransactionDate", "Value": 20241210120000}
                        ]
                    }
                }
            }
        }

        # Process it through your callback handler
        from django.http import HttpRequest
        test_request = HttpRequest()
        test_request.method = 'POST'
        test_request._body = json.dumps(simulated_callback).encode()

        response = mpesa_stk_callback(test_request)

        messages.success(request, f"Test callback processed! Loan #{loan_id} updated with payment of ${amount}")
        return redirect('my_loans')

    return JsonResponse({"error": "Invalid request"}, status=400)
@login_required
def bnotifications(request):
    notes = Notification.objects.filter(
        user=request.user,
        role="borrower"
    ).order_by("-created_at")

    unread_count = notes.filter(read=False).count()

    return render(request, "borrower/bnotifications.html", {
        "notifications": notes,
        "unread_count": unread_count,
    })

@login_required
def lnotifications(request):
    notes = Notification.objects.filter(
        user=request.user,
        role="lender"
    ).order_by("-created_at")

    unread_count = notes.filter(read=False).count()

    return render(request, "lender/lnotifications.html", {
        "notifications": notes,
        "unread_count": unread_count,
    })

@login_required
def bsettings(request):
    return render(request, "borrower/bsettings.html")
@login_required
def borrower(request):
    """Borrower dashboard showing loans, stats, and recent activity."""

    # Get all loans for this user
    loans = Loan.objects.filter(user=request.user).order_by('-created_at')

    # Stats calculations
    total_borrowed = sum([l.amount for l in loans])
    active_loans_count = loans.filter(status='Active', closed=False).count()
    total_outstanding = sum([
        (l.amount + (l.amount * l.interest_rate / 100) - l.paid_amount)
        for l in loans if l.status == 'Active'
    ])

    # Stats for dashboard
    stats = [
        {'title': 'Total Borrowed', 'value': total_borrowed, 'icon': '💰'},
        {'title': 'Active Loans', 'value': active_loans_count, 'icon': '📊'},
        {'title': 'Total Outstanding', 'value': total_outstanding, 'icon': '⚠️'},
    ]

    # Build loan objects compatible with your template
    loans_data = []
    for loan in loans:
        loans_data.append({
            'id': loan.id,
            'amount': loan.amount,
            'status': loan.status,
            'progress_percent': loan.progress_percent,  # Model @property
            'paid_amount': loan.paid_amount,
            'interest_rate': loan.interest_rate,
            'next_payment': getattr(loan, "next_payment", None),
        })

    # Recent activities: payments only
    recent_activity = [
        {
            'date': payment.created_at.strftime('%b %d, %Y'),
            'description': f"Repayment for Loan #{payment.loan.id}",
            'amount': payment.amount,
            'type': 'payment'
        }
        for payment in LoanPayment.objects.filter(user=request.user)
                                          .order_by('-created_at')[:5]
    ]

    context = {
        'stats': stats,
        'loans': loans_data,
        'recent_activity': recent_activity,
    }

    return render(request, 'borrower.html', context)
@login_required
def lender(request):
    """
    Lender dashboard with real statistics and data
    """
    if request.user.role != "lender":
        return redirect("borrower")

    # Get all loans funded by this lender
    funded_loans = Loan.objects.filter(lender=request.user)
    active_loans = funded_loans.filter(status='Active', closed=False)

    # Calculate Total Invested
    total_invested = funded_loans.aggregate(
        total=Coalesce(Sum('amount'), Decimal('0.00'))
    )['total']

    # Calculate Total Earnings (interest from all loans)
    total_earnings = funded_loans.aggregate(
        total=Coalesce(
            Sum((F('amount') * F('interest_rate') / 100), output_field=DecimalField()),
            Decimal('0.00')
        )
    )['total']

    # Calculate Actual Earnings (from payments received)
    actual_earnings = funded_loans.aggregate(
        total=Coalesce(
            Sum(F('paid_amount') - F('amount'), output_field=DecimalField()),
            Decimal('0.00')
        )
    )['total']
    # Ensure non-negative
    if actual_earnings < 0:
        actual_earnings = Decimal('0.00')

    # Active loans count
    active_loans_count = active_loans.count()

    # Pending loan requests (applications not yet processed)
    pending_requests = LoanApplication.objects.filter(status='pending').count()

    # Recent Activity - Last 5 transactions
    recent_loans = funded_loans.order_by('-funded_date')[:5]
    activities = []
    for loan in recent_loans:
        activities.append({
            'name': f"{loan.user.get_full_name()} - {loan.purpose}",
            'date': loan.funded_date.strftime('%b %d, %Y') if loan.funded_date else 'N/A',
            'amount': f"${loan.amount:,.2f}",
            'status': loan.status
        })

    # Portfolio Overview - Distribution by loan purpose
    from django.db.models import Count, Sum as DbSum

    portfolio_data = funded_loans.values('purpose').annotate(
        count=Count('id'),
        total_amount=DbSum('amount')
    ).order_by('-total_amount')

    # Calculate percentages for portfolio
    portfolio = []
    if total_invested > 0:
        for item in portfolio_data[:5]:  # Top 5 categories
            percentage = (item['total_amount'] / total_invested) * 100
            portfolio.append({
                'category': item['purpose'].title(),
                'percentage': round(percentage, 1),
                'amount': item['total_amount']
            })

    # Calculate growth percentages (placeholder - you can implement actual calculation)
    # For now, we'll calculate based on recent vs older loans
    from datetime import timedelta
    from django.utils import timezone

    thirty_days_ago = timezone.now() - timedelta(days=30)

    recent_invested = funded_loans.filter(
        funded_date__gte=thirty_days_ago
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0.00')))['total']

    older_invested = funded_loans.filter(
        funded_date__lt=thirty_days_ago
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0.00')))['total']

    if older_invested > 0:
        investment_growth = ((recent_invested / older_invested) * 100)
    else:
        investment_growth = 0 if recent_invested == 0 else 100

    context = {
        'name': request.user.username,
        'total_invested': f"{total_invested:,.2f}",
        'total_earnings': f"{total_earnings:,.2f}",
        'actual_earnings': f"{actual_earnings:,.2f}",
        'active_loans_count': active_loans_count,
        'pending_requests': pending_requests,
        'activities': activities,
        'portfolio': portfolio,
        'investment_growth': round(investment_growth, 1),
    }

    return render(request, "lender.html", context)
@login_required
def admin(request):
     return render(request, "admin.html", {"name": request.user.username})
@login_required
def loan_requests(request):
    if request.user.role != "lender":
        return redirect("dashboard")

    pending = LoanApplication.objects.filter(status="pending")

    return render(request, "lender/loan_requests.html", {
        "requests": pending
    })
def calculate_monthly_payment(amount, duration, interest_rate=Decimal("8.00")):
    monthly_rate = interest_rate / Decimal(100 * 12)
    return (amount * monthly_rate) / (1 - (1 + monthly_rate) ** (-duration))
@login_required
def fund_loan(request, application_id):
    # Only lenders can fund
    if request.user.role != "lender":
        messages.error(request, "Only lenders can fund loans.")
        return redirect("dashboard")

    application = get_object_or_404(LoanApplication, id=application_id)

    # Prevent funding already approved/rejected applications
    if application.status != "pending":
        messages.error(request, "This loan request has already been processed.")
        return redirect("loan_requests")

    # Calculate monthly payment using Loan model helper
    temp_loan = Loan(
        amount=application.amount,
        duration=application.duration,
        interest_rate=application.interest_rate
    )

    # Create Loan record
    loan = Loan.objects.create(
        user=application.user,
        amount=application.amount,
        purpose=application.purpose,
        duration=application.duration,
        interest_rate=application.interest_rate,
        start_date=timezone.now().date(),
        paid_amount=Decimal('0.00'),
        closed=False,
        status="Active",
        application_id=application.id,  # link back to LoanApplication
        lender=request.user,
        funded_date=timezone.now().date()
    )


    # Update the LoanApplication
    application.status = "approved"
    application.lender = request.user
    application.save()

    messages.success(request, f"Loan #{loan.id} funded successfully!")
    return redirect("loan_requests")
@login_required
def reject_loan(request, application_id):
    if request.user.role != "lender":
        return redirect("dashboard")

    try:
        app = LoanApplication.objects.get(id=application_id)
        app.status = "rejected"
        app.lender = request.user
        app.save()
        messages.success(request, "Loan request rejected.")
    except LoanApplication.DoesNotExist:
        messages.error(request, "Loan request not found.")

    return redirect("loan_requests")
@login_required
def approved_loans(request):
    """
    Shows all loans funded by the logged-in lender.
    Calculates totals for dashboard summary cards.
    """
    # Only loans funded by this lender
    loans = Loan.objects.filter(lender=request.user).order_by('-funded_date')

    # Totals
    total_funded = loans.aggregate(
        total=Coalesce(Sum('amount'), Decimal('0.00'))
    )['total']

    # Outstanding balance = sum of remaining amounts
    outstanding_balance = loans.aggregate(
        total=Coalesce(Sum(F('amount') - F('paid_amount'), output_field=DecimalField()), Decimal('0.00'))
    )['total']

    # Expected interest = sum of total interest for all loans
    expected_interest = loans.aggregate(
        total=Coalesce(Sum((F('amount') * F('interest_rate') / 100), output_field=DecimalField()), Decimal('0.00'))
    )['total']

    total_loans = loans.count()

    context = {
        'loans': loans,  # Changed from 'l' to 'loans'
        'total_funded': total_funded,
        'outstanding_balance': outstanding_balance,
        'expected_interest': expected_interest,
        'total_loans': total_loans,
    }

    # Make sure this matches your template file name
    return render(request, 'lender/approved_loans.html', context)
def wallet(request):
     return render(request, "lender/wallet.html")
@login_required
def fund_wallet(request):
    wallets, created = LenderWallet.objects.get_or_create(lender=request.user)

    if request.method == "POST":
        amount = float(request.POST.get("amount"))
        wallets.balance += amount
        wallets.save()

        Transaction.objects.create(
            lender=request.user,
            amount=amount,
            type="deposit"
        )

        return redirect("fund_wallet")

    return render(request, "lender/fund_wallet.html", {"wallet": wallets})
@login_required
def transaction_history(request):
    """
    Display complete transaction history for the lender including:
    - Loan funding (outflow)
    - Loan repayments (inflow)
    - Wallet deposits (inflow)
    - Wallet withdrawals (outflow)
    """
    if request.user.role != "lender":
        return redirect("borrower")

    # Get all transactions from different sources
    transactions_list = []

    # 1. Wallet Transactions (deposits)
    wallet_transactions = Transaction.objects.filter(
        lender=request.user
    ).order_by('-timestamp')

    for txn in wallet_transactions:
        transactions_list.append({
            'type': f'Wallet {txn.type.title()}',
            'borrower': 'Self',
            'status': 'Completed',
            'amount': float(txn.amount),
            'balance': 0,  # We'll calculate running balance later
            'date': txn.timestamp.strftime('%b %d, %Y'),
            'time': txn.timestamp.strftime('%I:%M %p'),
            'timestamp': txn.timestamp,
            'positive': True,  # Deposits are positive
        })

    # 2. Loans Funded (outflow)
    funded_loans = Loan.objects.filter(
        lender=request.user
    ).order_by('-funded_date')

    for loan in funded_loans:
        if loan.funded_date:
            transactions_list.append({
                'type': 'Loan Funded',
                'borrower': loan.user.get_full_name() or loan.user.username,
                'status': loan.status,
                'amount': float(loan.amount),
                'balance': 0,
                'date': loan.funded_date.strftime('%b %d, %Y'),
                'time': loan.funded_date.strftime('%I:%M %p'),
                'timestamp': loan.funded_date,
                'positive': False,  # Funding is outflow
            })

    # 3. Loan Repayments (inflow)
    # Get all payments for loans funded by this lender
    loan_payments = LoanPayment.objects.filter(
        loan__lender=request.user
    ).select_related('loan', 'user').order_by('-created_at')

    for payment in loan_payments:
        transactions_list.append({
            'type': 'Loan Repayment',
            'borrower': payment.user.get_full_name() or payment.user.username,
            'status': 'Completed',
            'amount': float(payment.amount),
            'balance': 0,
            'date': payment.created_at.strftime('%b %d, %Y'),
            'time': payment.created_at.strftime('%I:%M %p'),
            'timestamp': payment.created_at,
            'positive': True,  # Repayments are inflow
        })

    # Sort all transactions by timestamp (newest first)
    transactions_list.sort(key=lambda x: x['timestamp'], reverse=True)

    # Calculate running balance (from oldest to newest, then reverse for display)
    running_balance = Decimal('0.00')
    reversed_txns = list(reversed(transactions_list))

    for txn in reversed_txns:
        if txn['positive']:
            running_balance += Decimal(str(txn['amount']))
        else:
            running_balance -= Decimal(str(txn['amount']))
        txn['balance'] = f"{running_balance:,.2f}"

    # Reverse back to newest first
    transactions_list = list(reversed(reversed_txns))

    # Calculate summary statistics
    total_transactions = len(transactions_list)

    # Transactions this month
    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    transactions_this_month = sum(
        1 for txn in transactions_list
        if txn['timestamp'] >= first_day_of_month
    )

    # Total inflow (repayments + deposits)
    total_inflow = sum(
        Decimal(str(txn['amount'])) for txn in transactions_list
        if txn['positive']
    )

    # Total outflow (loans funded + withdrawals)
    total_outflow = sum(
        Decimal(str(txn['amount'])) for txn in transactions_list
        if not txn['positive']
    )

    context = {
        'transactions': transactions_list,
        'total_transactions': total_transactions,
        'transactions_this_month': transactions_this_month,
        'total_inflow': f"{total_inflow:,.2f}",
        'total_outflow': f"{total_outflow:,.2f}",
    }

    return render(request, "lender/transaction_history.html", context)
def admin_panel(request):
    return render(request, "admin.html")
# loans/views.py
def loan_success(request):
    return render(request, 'loan_success.html')
@login_required
def export_csv(request):
    """
    Export lender's transaction history to CSV file
    """
    if request.user.role != "lender":
        return HttpResponse("Unauthorized", status=403)

    # Create the HttpResponse object with CSV headers
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions_export.csv"'

    writer = csv.writer(response)
    # Write header row
    writer.writerow(['Date', 'Time', 'Type', 'Borrower/Description', 'Status', 'Amount', 'Balance'])

    # Get all transactions (same logic as transaction_history view)
    transactions_list = []

    # 1. Wallet Transactions
    wallet_transactions = Transaction.objects.filter(
        lender=request.user
    ).order_by('-timestamp')

    for txn in wallet_transactions:
        transactions_list.append({
            'type': f'Wallet {txn.type.title()}',
            'borrower': 'Self',
            'status': 'Completed',
            'amount': float(txn.amount),
            'balance': 0,
            'date': txn.timestamp.strftime('%b %d, %Y'),
            'time': txn.timestamp.strftime('%I:%M %p'),
            'timestamp': txn.timestamp,
            'positive': True,
        })

    # 2. Loans Funded
    funded_loans = Loan.objects.filter(lender=request.user).order_by('-funded_date')

    for loan in funded_loans:
        if loan.funded_date:
            transactions_list.append({
                'type': 'Loan Funded',
                'borrower': loan.user.get_full_name() or loan.user.username,
                'status': loan.status,
                'amount': float(loan.amount),
                'balance': 0,
                'date': loan.funded_date.strftime('%b %d, %Y'),
                'time': loan.funded_date.strftime('%I:%M %p'),
                'timestamp': loan.funded_date,
                'positive': False,
            })

    # 3. Loan Repayments
    loan_payments = LoanPayment.objects.filter(
        loan__lender=request.user
    ).select_related('loan', 'user').order_by('-created_at')

    for payment in loan_payments:
        transactions_list.append({
            'type': 'Loan Repayment',
            'borrower': payment.user.get_full_name() or payment.user.username,
            'status': 'Completed',
            'amount': float(payment.amount),
            'balance': 0,
            'date': payment.created_at.strftime('%b %d, %Y'),
            'time': payment.created_at.strftime('%I:%M %p'),
            'timestamp': payment.created_at,
            'positive': True,
        })

    # Sort by timestamp (oldest first for balance calculation)
    transactions_list.sort(key=lambda x: x['timestamp'])

    # Calculate running balance
    running_balance = Decimal('0.00')
    for txn in transactions_list:
        if txn['positive']:
            running_balance += Decimal(str(txn['amount']))
        else:
            running_balance -= Decimal(str(txn['amount']))
        txn['balance'] = float(running_balance)

    # Reverse to show newest first in export
    transactions_list.reverse()

    # Write transaction rows
    for txn in transactions_list:
        amount_str = f"{'+' if txn['positive'] else '-'}${txn['amount']:,.2f}"
        balance_str = f"${txn['balance']:,.2f}"

        writer.writerow([
            txn['date'],
            txn['time'],
            txn['type'],
            txn['borrower'],
            txn['status'],
            amount_str,
            balance_str
        ])

    return response
@login_required
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.read = True
    notification.save()
    return redirect(request.META.get('HTTP_REFERER', '/'))

@login_required
def settings_view(request):
    profile = request.user
    notifications = request.user.notifications

    return render(request, "borrower/bsettings.html", {
        "profile": profile,
        "notifications": notifications,
    })
@login_required
def update_profile(request):
    if request.method == "POST":
        user = request.user

        # Update User fields
        user.first_name = request.POST.get("first_name")
        user.last_name = request.POST.get("last_name")
        user.email = request.POST.get("email")
        user.save()

        # Update Profile fields
        user.phone = request.POST.get("phone")
        user.save()
        messages.success(request, "Profile updated successfully!")

    return redirect("settings")
@login_required
def change_password(request):
    if request.method == "POST":
        user = request.user
        current = request.POST.get("current_password")
        new = request.POST.get("new_password")
        confirm = request.POST.get("confirm_password")

        if not user.check_password(current):
            messages.error(request, "Current password incorrect.")
            return redirect("settings")

        if new != confirm:
            messages.error(request, "Passwords do not match.")
            return redirect("settings")

        user.set_password(new)
        user.save()

        update_session_auth_hash(request, user)

        messages.success(request, "Password updated!")
        return redirect("bsettings")
@login_required
def update_notifications(request):
    if request.method == "POST":
        n = request.user.notifications

        n.email_notifications = bool(request.POST.get("email_notifications"))
        n.sms_notifications = bool(request.POST.get("sms_notifications"))
        n.push_notifications = bool(request.POST.get("push_notifications"))

        n.loan_updates = bool(request.POST.get("loan_updates"))
        n.payment_reminders = bool(request.POST.get("payment_reminders"))
        n.promotions = bool(request.POST.get("promotions"))

        n.save()
        messages.success(request, "Notification preferences saved!")

    return redirect("bsettings")
@login_required
def update_privacy(request):
    if request.method == "POST":
        p = request.user

        p.profile_visibility = bool(request.POST.get("profile_visibility"))
        p.activity_status = bool(request.POST.get("activity_status"))
        p.analytics_enabled = bool(request.POST.get("analytics_enabled"))

        p.save()
        messages.success(request, "Privacy settings updated!")

    return redirect("settings")
@login_required
def download_my_data(request):
    user = request.user

    data = f"""
    Name: {user.first_name} {user.last_name}
    Email: {user.email}
    Phone: {user.phone}
    """

    response = HttpResponse(data, content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename="my_data.txt"'
    return response
@login_required
def delete_account(request):
    request.user.delete()
    messages.success(request, "Your account has been deleted.")
    return redirect("home")

@login_required
def lsettings_view(request):
    profile = request.user
    notifications = request.user.notifications

    return render(request, "lender/lsettings.html", {
        "profile": profile,
        "notifications": notifications,
    })
@login_required
def lupdate_profile(request):
    if request.method == "POST":
        user = request.user

        # Update User fields
        user.first_name = request.POST.get("first_name")
        user.last_name = request.POST.get("last_name")
        user.email = request.POST.get("email")
        user.save()

        # Update Profile fields
        user.phone = request.POST.get("phone")
        user.save()
        messages.success(request, "Profile updated successfully!")

    return redirect("lsettings")
@login_required
def lchange_password(request):
    if request.method == "POST":
        user = request.user
        current = request.POST.get("current_password")
        new = request.POST.get("new_password")
        confirm = request.POST.get("confirm_password")

        if not user.check_password(current):
            messages.error(request, "Current password incorrect.")
            return redirect("lsettings")

        if new != confirm:
            messages.error(request, "Passwords do not match.")
            return redirect("lsettings")

        user.set_password(new)
        user.save()

        update_session_auth_hash(request, user)

        messages.success(request, "Password updated!")
        return redirect("lsettings")
@login_required
def lupdate_notifications(request):
    if request.method == "POST":
        n = request.user.notifications

        n.email_notifications = bool(request.POST.get("email_notifications"))
        n.sms_notifications = bool(request.POST.get("sms_notifications"))
        n.push_notifications = bool(request.POST.get("push_notifications"))

        n.loan_updates = bool(request.POST.get("loan_updates"))
        n.payment_reminders = bool(request.POST.get("payment_reminders"))
        n.promotions = bool(request.POST.get("promotions"))

        n.save()
        messages.success(request, "Notification preferences saved!")

    return redirect("lsettings")
@login_required
def lupdate_privacy(request):
    if request.method == "POST":
        p = request.user

        p.profile_visibility = bool(request.POST.get("profile_visibility"))
        p.activity_status = bool(request.POST.get("activity_status"))
        p.analytics_enabled = bool(request.POST.get("analytics_enabled"))

        p.save()
        messages.success(request, "Privacy settings updated!")

    return redirect("lsettings")
@login_required
def ldownload_my_data(request):
    user = request.user

    data = f"""
    Name: {user.first_name} {user.last_name}
    Email: {user.email}
    Phone: {user.phone}
    """

    response = HttpResponse(data, content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename="my_data.txt"'
    return response
@login_required
def ldelete_account(request):
    request.user.delete()
    messages.success(request, "Your account has been deleted.")
    return redirect("home")


