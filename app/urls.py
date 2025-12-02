from django.contrib.auth.views import LogoutView
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_user, name='login'),
    path("logout/", LogoutView.as_view(next_page="login"), name="logout"),
    path("borrower/notifications/", views.notifications, name="notifications"),
    path("lender/lnotifications", views.lnotifications, name="lnotifications"),
    path("profile/", views.profile, name="profile"),
    path('register/', views.register, name='register'),
    path('apply/', views.apply_loan, name='apply_loan'),
    path('success/', views.loan_success, name='loan_success'),
    path('borrower/', views.borrower, name='borrower'),
    path("borrower/apply-loan/", views.apply_loan, name="apply_loan"),
    path("borrower/my-loans/", views.my_loans, name="my_loans"),
    path("borrower/repay-loan/", views.repay_loan, name="repay_loan"),
    path("lender/wallet/", views.wallet, name="wallet"),
    path('lender/', views.lender, name='lender'),
    path("lender/loan-requests/", views.loan_requests, name="loan_requests"),
    path("lender/approve/", views.approve_loan, name="approve_loan"),
    path("lender/reject/", views.reject_loan, name="reject_loan"),
    path("lender/fund-wallet/", views.fund_wallet, name="fund_wallet"),
    path("lender/transactions/", views.transaction_history, name="transaction_history"),
    path('export-csv/', views.export_csv, name='export_csv'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),
path('notifications/read/', views.mark_notification_read, name='mark_notification_read')

]
