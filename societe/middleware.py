from django.shortcuts import redirect
from django.urls import reverse


class FirstLoginRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                # On vérifie si l'utilisateur a un profil employé lié
                employe = request.user.profil_employe

                # Chemins autorisés (pour éviter les boucles infinies)
                path_changement = reverse('admin:password_change')
                path_done = reverse('admin:password_change_done')
                path_logout = reverse('admin:logout')

                # Si l'employé doit changer son MDP et n'est pas déjà sur la page de changement
                if employe.doit_changer_mot_de_passe:
                    if request.path not in [path_changement, path_done, path_logout]:
                        return redirect(path_changement)
            except:
                # Si l'utilisateur n'est pas un employé (ex: superuser), on ne fait rien
                pass

        return self.get_response(request)