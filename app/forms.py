# loans/forms.py
from django import forms
from .models import User
from .models import LoanApplication
from decimal import Decimal

class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'role']

class PasswordChangeForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput)
    new_password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)



class LoanApplicationForm(forms.ModelForm):
    class Meta:
        model = LoanApplication
        fields = ['amount', 'purpose', 'duration', 'monthly_income', 'employment_status', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

