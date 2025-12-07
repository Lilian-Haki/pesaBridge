import json
from decimal import Decimal
from app.mpesa.stk_push import lipa_na_mpesa_stk_push
import requests
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from requests.auth import HTTPBasicAuth
from .utils.mpesa import get_mpesa_access_token, generate_stk_password
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db.models import Sum, DecimalField, F
from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate,login,get_user_model
from .models import Notification, LenderWallet, Transaction, Loan, LoanApplication, LoanPayment
from django.contrib.auth.hashers import make_password
from django.http import HttpResponse
import csv
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import LoanApplicationForm
from django.http import JsonResponse, HttpResponseBadRequest
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
    active_loans = Loan.objects.filter(user=request.user, status="Active")
    selected_loan_data = None

    if request.method == "POST":
        loan_id = request.POST.get("loan")
        amount = request.POST.get("amount")

        if not loan_id or not amount:
            messages.error(request, "Please select a loan and enter an amount.")
            return redirect("repay_loan")

        try:
            amount = Decimal(amount)
        except:
            messages.error(request, "Invalid amount")
            return redirect("repay_loan")

        try:
            loan = Loan.objects.get(id=loan_id, user=request.user)
        except Loan.DoesNotExist:
            messages.error(request, "Loan not found.")
            return redirect("repay_loan")

        if amount > loan.balance:
            messages.error(request, "Payment exceeds outstanding loan balance.")
            return redirect("repay_loan")

        # Format phone
        phone = request.user.phone
        if phone.startswith("07"):
            phone = "254" + phone[1:]

        # STK PUSH
        response = lipa_na_mpesa_stk_push(
            phone=phone,
            amount=amount,
            account_reference=f"Loan-{loan.id}",
            description="Loan Repayment",
        )

        if response.get("ResponseCode") == "0":
            messages.success(request, "Check your phone and enter your M-Pesa PIN.")
        else:
            messages.error(request, "Failed to initiate STK push.")

        return redirect("repay_loan")

    # GET selected loan
    loan_id = request.GET.get("loan_id")
    if loan_id:
        selected_loan_data = Loan.objects.filter(id=loan_id, user=request.user).first()

    return render(request, "borrower/repay_loan.html", {
        "active_loans": active_loans,
        "selected_loan_data": selected_loan_data,
    })

@csrf_exempt
def mpesa_stk_callback(request):
    data = json.loads(request.body.decode('utf-8'))

    stk = data["Body"]["stkCallback"]
    result_code = stk["ResultCode"]

    if result_code != 0:
        return JsonResponse({"message": "Payment failed"}, status=200)

    callback_items = stk["CallbackMetadata"]["Item"]

    amount = callback_items[0]["Value"]
    phone = callback_items[4]["Value"]

    account_ref = data["Body"]["stkCallback"].get("AccountReference", "")
    loan_id = account_ref.split("-")[1]

    loan = Loan.objects.get(id=loan_id)

    loan.paid_amount += Decimal(amount)
    if loan.paid_amount >= loan.amount:
        loan.status = "Completed"
        loan.closed = True
    loan.save()

    return JsonResponse({"message": "Payment recorded"}, status=200)


@login_required
def notifications(request):
    notes = [
        {"message": "Loan repayment due Dec 5", "read": False},
        {"message": "New loan offer available", "read": True},
    ]
    unread_count = sum(1 for n in notes if not n["read"])
    return render(request, "borrower/notifications.html", {
        "notifications": notes,
        "unread_count": unread_count,
    })

@login_required
def lnotifications(request):
    notes = [
        {"message": "Loan repayment due Dec 5", "read": False},
        {"message": "New loan offer available", "read": True},
    ]
    unread_count = sum(1 for n in notes if not n["read"])
    return render(request, "lender/l_notification.html", {
        "notifications": notes,
        "unread_count": unread_count,
    })

@login_required
def profile(request):
    return render(request, "profile.html", {"user": request.user})

@login_required
def borrower(request):
     return render(request, "borrower.html", {"name": request.user.username})


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

    from datetime import datetime, timedelta

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

