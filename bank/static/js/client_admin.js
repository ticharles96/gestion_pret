(function($) {
    $(document).ready(function() {
        function toggleRaison() {
            // id_statut_dossier est l'ID généré par Django pour le champ statut
            var statut = $('#id_statut_dossier').val();
            // .field-raison_blocage est la classe de la ligne entière dans l'admin
            var row = $('.field-raison_blocage');

            if (statut === 'BLOQUE') {
                row.show();
            } else {
                row.hide();
            }
        }

        // Écouter les changements
        $('#id_statut_dossier').change(function() {
            toggleRaison();
        });

        // Lancer au démarrage pour les dossiers déjà bloqués
        toggleRaison();
    });
})(django.jQuery);