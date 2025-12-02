from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate,login
from .forms import RegisterForm
from .models import Notification, Loan, Transaction, LenderWallet,Transaction
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.http import HttpResponse
import csv

# Create your views here.
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


User = get_user_model()

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
def my_loans(request):
     return render(request, "borrower/my_loans.html")

@login_required
def repay_loan(request):
     return render(request, "borrower/repay_loan.html")

@login_required
def wallet(request):
     return render(request, "lender/wallet.html")

@login_required
def loan_requests(request):
    loans = Loan.objects.filter(status="pending")

    for loan in loans:
        # transform risk score into risk level
        if loan.risk_score >= 75:
            loan.risk_level = "Low"
        elif loan.risk_score >= 40:
            loan.risk_level = "Medium"
        else:
            loan.risk_level = "High"
    return render(request, "lender/loan_requests.html", {"loans": loans})

@login_required
def approve_loan(request):
        return render(request,"lender/approve_loan.html")

@login_required
def reject_loan(request):
    return redirect("approve_loan")

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

def apply_loan(request):
    # if request.method == 'POST':
    #     form = LoanApplicationForm(request.POST)
    #     if form.is_valid():
    #         form.save()
    #         return redirect('loan_success')
    # else:
    #     form = LoanApplicationForm()
    return render(request, 'borrower/apply_loan.html')

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

