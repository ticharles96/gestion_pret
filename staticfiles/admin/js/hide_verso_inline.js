(function() {
    'use strict';
    document.addEventListener('DOMContentLoaded', function() {

        function applyLogic() {
            // 1. On cherche le selecteur de type de pièce
            const typePieceField = document.querySelector('select[name$="type_piece"]');

            // 2. On cherche l'input du verso
            const versoInput = document.querySelector('input[name$="piece_identite_verso"]');

            if (!typePieceField || !versoInput) {
                console.log("Éléments non trouvés...");
                return;
            }

            // 3. On remonte au conteneur le plus proche (la colonne ou la ligne)
            const versoContainer = versoInput.closest('.field-piece_identite_verso') || versoInput.closest('.column');

            function toggle() {
                console.log("Type choisi :", typePieceField.value);
                if (typePieceField.value === 'PASSEPORT') {
                    versoContainer.style.display = 'none';
                } else {
                    versoContainer.style.display = 'block';
                }
            }

            typePieceField.addEventListener('change', toggle);
            toggle(); // Exécution initiale
        }

        // On attend un tout petit peu que Django finisse de rendre l'inline
        setTimeout(applyLogic, 100);
    });
})();