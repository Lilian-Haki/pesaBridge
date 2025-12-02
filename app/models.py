from django.contrib.auth.decorators import login_required
from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
# loans/models.py

class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True, null=True)
    ROLE_CHOICES = (
        ('borrower', 'Borrower'),
        ('lender', 'Lender'),
        ('admin', 'Admin'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('payment', 'Payment'),
        ('offer', 'Offer'),
        ('other', 'Other'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=NOTIFICATION_TYPES, default='other')
    title = models.CharField(max_length=100)
    message = models.TextField()
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type} - {self.title}"

class LoanApplication(models.Model):
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    loan_purpose = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.amount}"


class LenderWallet(models.Model):
    lender = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)


class Loan(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("funded", "Funded"),
        ("active", "Active"),
        ("completed", "Completed"),
    )

    borrower = models.ForeignKey(User, on_delete=models.CASCADE, related_name="borrower_loans")
    lender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="lender_loans")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    duration_months = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    risk_score = models.IntegerField(default=50)  # 0–100
    risk_level = models.CharField(max_length=20, default="Medium")  # Auto-calculated later
    purpose = models.CharField(max_length=255, null=True, blank=True)

class Transaction(models.Model):
    lender = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=20) # deposit, funding
    timestamp = models.DateTimeField(auto_now_add=True)
