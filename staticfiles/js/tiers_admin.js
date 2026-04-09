document.addEventListener('DOMContentLoaded', function() {
    const typeField = document.querySelector('#id_type_piece');
    // On récupère la ligne (row) qui contient le champ verso
    const rowVerso = document.querySelector('.field-piece_verso');

    function manageDisplay() {
        if (!typeField || !rowVerso) return; // Sécurité si les champs n'existent pas

        const choice = typeField.value;

        // On affiche le Verso UNIQUEMENT pour NINU et PERMIS
        // Notez l'orthographe de 'Acte de naissance' avec deux "s"
        if (choice === 'NINU' || choice === 'PERMIS') {
            rowVerso.style.display = 'block';
        } else {
            rowVerso.style.display = 'none';document.addEventListener('DOMContentLoaded', function() {
    // 1. On récupère le menu déroulant (ID généré par Django : id_ + nom du champ)
    const typeField = document.querySelector('#id_type_piece_identite');

    // 2. On récupère la ligne complète du champ Verso
    const rowVerso = document.querySelector('.field-piece_identite_verso');

    function manageDisplay() {
        if (!typeField || !rowVerso) return;

        const choice = typeField.value;

        // Logique : SEULS 'NINU' et 'PERMIS' affichent le verso
        // 'Acte de naissance', 'NIF' et 'PASSEPORT' ne l'affichent pas
        if (choice === 'NINU' || choice === 'PERMIS') {
            rowVerso.style.display = 'block';
        } else {
            rowVerso.style.display = 'none';
        }
    }

    if (typeField) {
        typeField.addEventListener('change', manageDisplay);
        manageDisplay(); // Exécution immédiate au chargement
    }
});
        }
    }

    if (typeField) {
        typeField.addEventListener('change', manageDisplay);
        manageDisplay(); // Important : exécuter au chargement pour les modifs
    }
});


document.addEventListener('DOMContentLoaded', function() {
    // On cherche le champ téléphone par son ID Django par défaut
    const phoneInput = document.querySelector("#id_telephone");

    if (phoneInput) {
        const iti = window.intlTelInput(phoneInput, {
            initialCountry: "ht", // Haïti par défaut
            separateDialCode: true, // Affiche +509 à côté du drapeau
            preferredCountries: ["ht", "us", "ca", "fr"], // Pays fréquents pour Haïti
            utilsScript: "https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/17.0.19/js/utils.js"
        });

        // Sécurité : avant d'enregistrer, on met le numéro au format international
        const form = phoneInput.closest('form');
        form.addEventListener('submit', function() {
            if (phoneInput.value.trim()) {
                phoneInput.value = iti.getNumber();
            }
        });
    }
});