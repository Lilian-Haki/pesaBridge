from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from django.core.validators import MinValueValidator
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

class LenderWallet(models.Model):
    lender = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)


# class Loan(models.Model):
#     STATUS_CHOICES = (
#         ("pending", "Pending"),
#         ("approved", "Approved"),
#         ("rejected", "Rejected"),
#         ("funded", "Funded"),
#         ("active", "Active"),
#         ("completed", "Completed"),
#     )
#
#     borrower = models.ForeignKey(User, on_delete=models.CASCADE, related_name="borrower_loans")
#     lender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="lender_loans")
#     amount = models.DecimalField(max_digits=12, decimal_places=2)
#     duration_months = models.IntegerField()
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
#     created_at = models.DateTimeField(auto_now_add=True)
#     risk_score = models.IntegerField(default=50)  # 0–100
#     risk_level = models.CharField(max_length=20, default="Medium")  # Auto-calculated later
#     purpose = models.CharField(max_length=255, null=True, blank=True)

class Transaction(models.Model):
    lender = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=20) # deposit, funding
    timestamp = models.DateTimeField(auto_now_add=True)



LOAN_STATUS = (
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('closed', 'Closed'),
)

APPLICATION_STATUS = (
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
)

PAYMENT_METHODS = (
    ('card', 'Card'),
    ('bank', 'Bank Transfer'),
    ('wallet', 'Wallet'),
)

class LoanApplication(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loan_applications')
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(1)])
    purpose = models.CharField(max_length=100)
    duration = models.PositiveIntegerField(help_text="Duration in months")
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('8.00')
    )
    employment_status = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=APPLICATION_STATUS, default='pending')
    lender = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="loan_app_requests"
    )
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Application #{self.pk} - {self.user} - {self.purpose} - {self.duration}- {self.monthly_income} - {self.employment_status} - {self.description} - {self.status}"

class Loan(models.Model):
    @property
    def progress_percent(self):
        if self.amount == 0:
            return 0
        progress = (self.paid_amount / self.amount) * 100
        return float(round(progress, 2))

    application = models.OneToOneField(
        'LoanApplication',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='final_loan'
    )

    @property
    def monthly_payment(self):
        pv = self.amount
        n = self.duration
        monthly_rate = (self.interest_rate / 100) / 12
        if monthly_rate == 0:
            payment = pv / n
        else:
            payment = (monthly_rate * pv) / (1 - (1 + monthly_rate) ** -n)
        return round(payment, 2)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loans')
    lender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='funded_loans_v2')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    purpose = models.CharField(max_length=100)
    duration = models.PositiveIntegerField(help_text="Duration in months")
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('8.00'))
    start_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=LOAN_STATUS, default='pending')
    monthly_payment = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    closed = models.BooleanField(default=False)
    funded_date = models.DateTimeField(null=True, blank=True)  # will be set when lender funds the loan
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-funded_date']

    def __str__(self):
        return f"Loan #{self.pk} - {self.user.username} - ${self.amount}"


    @property
    def remaining_balance(self):
        return max(self.amount - self.paid_amount, Decimal('0.00'))

    @property
    def interest(self):
        return self.amount * (self.interest_rate / 100)

    @property
    def term(self):
        return self.duration

    @property
    def borrower(self):
        return self.user.get_full_name() or self.user.username

    @property
    def next_payment(self):
        # TODO: implement logic to calculate next payment date if needed
        return "N/A"




class Payment(models.Model):
    loan = models.ForeignKey('Loan', on_delete=models.CASCADE, related_name='payments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    reference = models.CharField(max_length=200, blank=True, null=True)  # optional transaction id
    created_at = models.DateTimeField(default=timezone.now)
    processed = models.BooleanField(default=False)

    def __str__(self):
        return f"Payment #{self.pk} - Loan {self.loan.pk} - {self.amount}"

    def apply(self):
        """
        Mark as processed and add to loan tally. Should be called after payment processor confirms success.
        """
        if not self.processed:
            self.loan.add_payment(self.amount)
            self.processed = True
            self.save(update_fields=['processed'])
