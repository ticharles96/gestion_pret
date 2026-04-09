from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

from bank.views import imprimer_contrat_pret
from parametres import views

urlpatterns = [
    # 1. Redirection de la racine vers l'admin (Évite la 404 au démarrage)
    path('', RedirectView.as_view(url='/admin/', permanent=True)),

    # 2. Django JET (Toujours avant l'admin standard)
    path('jet/', include('jet.urls', 'jet')),
    path('jet/dashboard/', include('jet.dashboard.urls', 'jet-dashboard')),

    # 3. Gestion des mots de passe (URLs sécurisées pour l'admin)
    path('admin/password_reset/', auth_views.PasswordResetView.as_view(), name='admin_password_reset'),
    path('admin/password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('admin/password_change/', auth_views.PasswordChangeView.as_view(success_url='/admin/'), name='password_change'),

    # 4. L'administration principale (Chemin explicite pour éviter les conflits)
    path('admin/', admin.site.urls),

    # 5. Vos routes spécifiques (Contrats, PDF, Chaining)
    path('admin/bank/pret/<int:pret_id>/pdf/', imprimer_contrat_pret, name='imprimer_contrat_pret'),
    path('chaining/', include('smart_selects.urls')),
    path('select2/', include('django_select2.urls')),
    path('tiers/<int:pk>/pdf/', views.tiers_pdf_view, name='profil_pdf'),
]

# 6. Gestion des fichiers Statiques et Médias (Logo)
# Note : En production sur le VPS (DEBUG=False), Apache prendra le relais
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)