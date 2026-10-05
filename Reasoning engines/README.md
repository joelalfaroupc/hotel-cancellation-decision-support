# Motors de raonament

El component de raonament està implementat dins del codi operatiu de l'IDSS:

- `../Interficie/idss_engine.py`
- `../Interficie/app.js`

El motor combina:

1. La probabilitat de cancel·lació estimada pel model XGBoost.
2. L'assignació del perfil de clustering TLP.
3. Les regles expertes definides a `../KnowledgeSources/reglas_negocio_idss_experto.yaml`.

No cal cap binari extern separat per al motor de raonament.
