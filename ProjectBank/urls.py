from django.contrib.auth import views as auth_views
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from bank.views import imprimer_contrat_pret
from parametres import views

urlpatterns = [
    # 1. Les routes JET en premier
    path('jet/', include('jet.urls', 'jet')),
    path('jet/dashboard/', include('jet.dashboard.urls', 'jet-dashboard')),

    # 2. LES ROUTES DE MOT DE PASSE (AVANT l'admin principal)
    # On ajoute aussi 'password_change' pour la première connexion
    path('admin/password_reset/', auth_views.PasswordResetView.as_view(), name='admin_password_reset'),
    path('admin/password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('admin/password_change/', auth_views.PasswordChangeView.as_view(success_url='/admin/'), name='password_change'),

# Ajout de la route pour le contrat PDF
    path('admin/bank/pret/<int:pret_id>/pdf/', imprimer_contrat_pret, name='imprimer_contrat_pret'),



    # 4. Les extensions (Select2, Chaining, etc.)
    path('chaining/', include('smart_selects.urls')),
    path('select2/', include('django_select2.urls')),
    path('tiers/<int:pk>/pdf/', views.tiers_pdf_view, name='profil_pdf'),
    # 3. L'administration principale
    path('', admin.site.urls),
    ]

# 5. SUPPORT MÉDIA (Pour le Logo)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)