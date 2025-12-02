# loans/forms.py
from django import forms
from .models import User

class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'role']

class PasswordChangeForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput)
    new_password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

# class LoanApplicationForm(forms.ModelForm):
#     class Meta:
#         model = LoanApplication
#         fields = ['full_name', 'email', 'phone_number', 'amount', 'loan_purpose']
#         widgets = {
#             'full_name': forms.TextInput(attrs={
#                 'class': 'w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500',
#                 'placeholder': 'Full Name'
#             }),
#             'email': forms.EmailInput(attrs={
#                 'class': 'w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500',
#                 'placeholder': 'Email'
#             }),
#             'phone_number': forms.TextInput(attrs={
#                 'class': 'w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500',
#                 'placeholder': 'Phone Number'
#             }),
#             'amount': forms.NumberInput(attrs={
#                 'class': 'w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500',
#                 'placeholder': 'Loan Amount'
#             }),
#             'loan_purpose': forms.Textarea(attrs={
#                 'class': 'w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500',
#                 'placeholder': 'Purpose of Loan',
#                 'rows': 4
#             }),
#         }
