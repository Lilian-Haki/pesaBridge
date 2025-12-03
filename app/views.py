from decimal import Decimal

from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db.models import Sum, DecimalField, F
from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate,login,get_user_model
from .models import Notification, LenderWallet, Transaction, Loan, LoanApplication
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
            return redirect('my_loans')
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
    active_loans_count = loans.filter(status='approved', closed=False).count()
    total_outstanding = sum([ (l.amount - l.paid_amount) for l in loans if l.status == 'approved'])

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
     return render(request, "lender.html", {"name": request.user.username})

@login_required
def admin(request):
     return render(request, "admin.html", {"name": request.user.username})


@login_required
def repay_loan(request):
     return render(request, "borrower/repay_loan.html")
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

# @login_required
# def approved_loans(request):
#     # Only loans funded by this lender (if applicable)
#     loans = Loan.objects.filter(lender=request.user, status='Active')
#
#     total_funded = sum([loan.amount for loan in loans])
#     total_loans = loans.count()
#     outstanding_balance = sum([loan.remaining_balance for loan in loans])
#     expected_interest = sum([loan.interest for loan in loans])
#
#     context = {
#         'loans': loans,
#         'total_funded': total_funded,
#         'total_loans': total_loans,
#         'outstanding_balance': outstanding_balance,
#         'expected_interest': expected_interest,
#     }
#
#     return render(request, 'lender/approve_loan.html', context)

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
        'loans': loans,
        'total_funded': total_funded,
        'outstanding_balance': outstanding_balance,
        'expected_interest': expected_interest,
        'total_loans': total_loans,
    }

    return render(request, 'lender/approve_loans.html', context)
@login_required
def wallet(request):
     return render(request, "lender/wallet.html")

@login_required
def approve_loan(request):
        return render(request,"lender/approve_loan.html")


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
    logs = Transaction.objects.filter(lender=request.user).order_by("-timestamp")
    return render(request, "lender/transaction_history.html", {"logs": logs})

def admin_panel(request):
    return render(request, "admin.html")
# loans/views.py


def loan_success(request):
    return render(request, 'loan_success.html')

def export_csv(request):
    # Create the HttpResponse object with CSV headers
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions.csv"'

    writer = csv.writer(response)
    writer.writerow(['Type', 'Borrower', 'Status', 'Amount', 'Balance', 'Date', 'Time'])

    for tx in Transaction.objects.all():
        writer.writerow([tx.type, tx.borrower, tx.status, tx.amount, tx.balance, tx.date, tx.time])

    return response
@login_required
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.read = True
    notification.save()
    return redirect(request.META.get('HTTP_REFERER', '/'))

