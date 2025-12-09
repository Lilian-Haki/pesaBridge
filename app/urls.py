from django.contrib.auth.views import LogoutView
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_user, name='login'),
    path("logout/", LogoutView.as_view(next_page="login"), name="logout"),
    path('register/', views.register, name='register'),
    path('mpesa/callback/', views.mpesa_stk_callback, name='mpesa_callback'),
    path('export-csv/', views.export_csv, name='export_csv'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),


    #BORROWER REDIRECTS
    path("borrower/bnotifications/", views.bnotifications, name="bnotifications"),
    path("borrower/bsettings/", views.bsettings, name="bsettings"),
    path('borrower/', views.borrower, name='borrower'),
    path("borrower/apply-loan/", views.apply_loan, name="apply_loan"),
    path("borrower/my-loans/", views.my_loans, name="my_loans"),
    path("borrower/repay-loan/", views.repay_loan, name="repay_loan"),


    #LENDER REDIRECTS
    path("lender/lnotifications/", views.lnotifications, name="lnotifications"),
    path('lender/', views.lender, name='lender'),
    path("lender/loan-requests/", views.loan_requests, name="loan_requests"),
    path("lender/fund/<int:application_id>/", views.fund_loan, name="fund_loan"),
    path("lender/reject/<int:application_id>/", views.reject_loan, name="reject_loan"),
    path("lender/approve/", views.approved_loans, name="approved_loans"),
    path("lender/fund-wallet/", views.fund_wallet, name="fund_wallet"),
    path("lender/transactions/", views.transaction_history, name="transaction_history"),
]
