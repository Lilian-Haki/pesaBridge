from django.shortcuts import render, redirect
from django.contrib.auth import authenticate,login
from .forms import LoanApplicationForm, RegisterForm
from .models import Notification, Loan, Transaction, LenderWallet
from django.contrib.auth.decorators import login_required

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

def register_user(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            login(request, user)

            # Redirect based on role
            if user.role == "borrower":
                return redirect("borrower")
            elif user.role == "lender":
                return redirect("lender")
            else:
                return redirect("admin")
    else:
        form = RegisterForm()

    return render(request, "register.html", {"form": form})

@login_required
def notifications(request):
    notes = [
        {"message": "Loan repayment due Dec 5", "read": False},
        {"message": "New loan offer available", "read": True},
    ]
    unread_count = sum(1 for n in notes if not n["read"])
    return render(request, "notifications.html", {
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
     return render(request, "borrower/wallet.html")

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
def approve_loan(request, loan_id):
    loan = Loan.objects.get(id=loan_id)

    loan.status = "approved"
    loan.lender = request.user
    loan.save()

    return redirect("loan_requests")

@login_required
def reject_loan(request, loan_id):
    loan = Loan.objects.get(id=loan_id)
    loan.status = "rejected"
    loan.save()

    return redirect("loan_requests")

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
    if request.method == 'POST':
        form = LoanApplicationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('loan_success')
    else:
        form = LoanApplicationForm()
    return render(request, 'loan_form.html', {'form': form})

def loan_success(request):
    return render(request, 'loan_success.html')

