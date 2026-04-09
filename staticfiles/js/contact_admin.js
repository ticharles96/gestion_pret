document.addEventListener('change', function(e) {
    if (e.target && e.target.name.includes('type_contact')) {
        // On récupère le champ "valeur" de la même ligne
        let row = e.target.closest('tr');
        let valeurInput = row.querySelector('input[name$="valeur"]');
        let choice = e.target.value;

        if (choice === 'email') {
            valeurInput.type = 'email';
            valeurInput.placeholder = 'exemple@mail.com';
        } else if (choice.includes('Telephone') || choice === 'whatsapp') {
            valeurInput.type = 'tel';
            valeurInput.placeholder = '+509 ...';
        } else if (choice === 'siteweb' || choice === 'facebook') {
            valeurInput.type = 'url';
            valeurInput.placeholder = 'https://...';
        } else {
            valeurInput.type = 'text';
            valeurInput.placeholder = '';
        }
    }
});


(function($) {
    $(document).ready(function() {
        function updateIconLink(row) {
            const select = row.find('select[id$="-type_contact"]');
            const input = row.find('input[id$="-valeur"]');
            const container = row.find('.field-icone_visuelle div, .field-icone_visuelle p, .readonly');

            const choice = select.val();
            const val = input.val();

            const config = {
                'email': { icon: 'fa-envelope', col: '#EA4335', pre: 'mailto:' },
                'whatsapp': { icon: 'fa-whatsapp', col: '#25D366', pre: 'https://wa.me/' },
                'siteweb': { icon: 'fa-globe', col: '#007bff', pre: '' },
                'Telephone Mobile': { icon: 'fa-mobile-screen', col: '#417690', pre: 'tel:' },
                'Telephone domicile': { icon: 'fa-phone', col: '#417690', pre: 'tel:' },
                'facebook': { icon: 'fa-facebook', col: '#1877F2', pre: '' }
            };

            const s = config[choice] || { icon: 'fa-circle-info', col: '#ccc', pre: '' };
            const href = val ? (s.pre + val) : '#';

            if (container.length) {
                container.html(`
                    <a href="${href}" target="_blank" class="contact-link">
                        <i class="fa-solid ${s.icon}" style="font-size: 1.2rem; color: ${s.col};"></i>
                    </a>
                `);
            }
        }

        // Écouter le changement de type OU la saisie dans le champ valeur
        $(document).on('change keyup', 'select[id$="-type_contact"], input[id$="-valeur"]', function() {
            updateIconLink($(this).closest('tr'));
        });

        // Initialisation pour les lignes existantes au chargement
        $('tr.has_original').each(function() {
            updateIconLink($(this));
        });
    });
})(django.jQuery);

// Détecter l'ajout d'une nouvelle ligne par l'utilisateur
$(document).on('formset:added', function(event, $row, formsetName) {
    // Initialiser l'icône par défaut pour la nouvelle ligne
    const select = $row.find('select[id$="-type_contact"]');
    updateIconLink($row);
});


(function($) {
    $(document).ready(function() {
        function togglePrincipalCheckbox(row) {
            const typeSelect = row.find('select[id$="-type_contact"]');
            const principalCheckbox = row.find('input[id$="-est_principal"]');
            const typeValue = typeSelect.val();

            // Liste des types téléphoniques
            const typesTel = ['Telephone Mobile', 'Telephone domicile', 'whatsapp'];

            if (typesTel.includes(typeValue)) {
                principalCheckbox.show().removeAttr('disabled');
                principalCheckbox.closest('td').css('opacity', '1');
            } else {
                // On décoche et on cache si ce n'est pas un téléphone
                principalCheckbox.prop('checked', false).hide().attr('disabled', 'disabled');
                principalCheckbox.closest('td').css('opacity', '0.3'); // Effet visuel "désactivé"
            }
        }

        // Écouter le changement de type
        $(document).on('change', 'select[id$="-type_contact"]', function() {
            togglePrincipalCheckbox($(this).closest('tr'));
        });

        // Gérer l'unicité de la coche entre les lignes
        $(document).on('change', 'input[id$="-est_principal"]', function() {
            if ($(this).is(':checked')) {
                $('input[id$="-est_principal"]').not(this).prop('checked', false);
            }
        });

        // Initialisation au chargement et pour les nouvelles lignes
        function initAllRows() {
            $('tr.has_original, .inline-related tr').each(function() {
                togglePrincipalCheckbox($(this));
            });
        }

        initAllRows();
        $(document).on('formset:added', function(e, $row) {
            togglePrincipalCheckbox($row);
        });
    });
})(django.jQuery);