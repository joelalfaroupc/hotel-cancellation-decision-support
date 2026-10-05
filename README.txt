PW234-PAID-2026-T8-IDSSHotels
================================

Aquesta carpeta és l'arrel de l'entrega PW4-D1. El contingut està organitzat
seguint l'estructura demanada per al lliurament: documentació, dades, fonts de
coneixement, models, motor de raonament, codi font, IDSS, demo i presentació.


Estructura de la carpeta
------------------------

Documentation/
  Conté la documentació final del projecte i els documents de gestió.

  - Architecture/Arquitectura.docx:
      Document d'arquitectura del sistema.

  - Architecture/Arquitectura IDSS.png:
      Esquema visual de l'arquitectura de l'IDSS.

  - Report.pdf:
      Informe final del projecte.

  - Canvas.pptx:
      Canvas del projecte.

  - Gantt_Final.pdf:
      Planificació final del projecte.

  - tasks_and_hours_project_final.xlsx:
      Full amb les tasques, dedicació i hores del projecte.


Data/
  Conté les dades utilitzades pel projecte i els conjunts preprocessats.

  - dataset_5000.csv:
      Dataset principal de treball utilitzat durant l'anàlisi i el modelatge.

  - hotel_clustering_output.csv:
      Resultat amb la informació de clustering aplicada a les reserves.

  - dades_preprocessades_ml/:
      Dades preparades per als models supervisats. Inclou X_train, X_val,
      X_test, y_train, y_val, y_test, el preprocessor.joblib i el resum del
      preprocessament.

  - dades_preprocessades_clustering/:
      Dataset preparat per al clustering i el seu resum de preprocessament.


KnowledgeSources/
  Conté la base de coneixement expert del sistema.

  - reglas_negocio_idss_experto.yaml:
      Regles de negoci utilitzades per l'IDSS per generar recomanacions i
      accions prescriptives.


Models/
  Conté els models entrenats, els resultats comparatius i els artefactes
  d'interpretabilitat.

  - baseline/:
      Resultats del millor model base i taula comparativa dels models inicials.

  - final_model/:
      Model final entrenat, resum del millor model i leaderboard final.

  - interpretability/:
      Sortides SHAP del model final: gràfics, importàncies globals i exemples
      locals.

  - model_comparison_test_metrics.csv:
      Comparació de mètriques sobre test.


Reasoning engines/
  Conté una nota explicativa sobre el motor de raonament. El motor executable no
  és un binari separat: està implementat dins del codi de l'IDSS, principalment
  a IDSS/Interficie/idss_engine.py i IDSS/Interficie/app.js.


Source/
  Conté el codi i notebooks utilitzats per preparar les dades, fer l'anàlisi,
  entrenar models i generar el clustering.

  - EDA.ipynb:
      Notebook d'anàlisi exploratòria de dades.

  - preprocessament.ipynb:
      Notebook de preprocessament.

  - clustering_kmeans_hdbscan.ipynb:
      Notebook de clustering.

  - train_model.py:
      Entrenament i comparació de models base.

  - train_model_cv.py:
      Entrenament, validació creuada i selecció del model final.


IDSS/
  Conté el sistema operatiu final. La interfície i la lògica principal són a
  IDSS/Interficie/.

  Fitxers principals dins d'IDSS/Interficie/:

  - index.html:
      Dashboard principal de l'IDSS.

  - reserva_web.html:
      Pàgina de simulació/entrada de reserva.

  - app.js:
      Lògica de la interfície, visualització de resultats i integració de les
      recomanacions.

  - styles.css:
      Estils de la interfície web.

  - idss_engine.py:
      Motor local que combina predicció, perfil de clustering i regles expertes.

  - generate_dashboard_data.py:
      Script per generar dades agregades del dashboard.

  - dashboard_data.js:
      Dades preparades per al dashboard.

  - model_artifacts/:
      Model final i fitxers associats necessaris per executar l'IDSS.

  - email_agent/:
      Backend local per a l'agent de correu i serveis relacionats.

  - reglas_negocio_idss_experto.yaml:
      Còpia de les regles expertes utilitzada per la interfície.

  - requirements.txt:
      Dependències principals de la interfície i motor local.

  - requirements-agent.txt:
      Dependències del backend local de l'agent de correu.

  - .env.example:
      Exemple de variables d'entorn per configurar el backend.

  - verify_app.mjs, verify_booking_page.mjs, verify_new_booking.mjs:
      Scripts de verificació amb Node/Playwright per revisar la interfície.


Demo/
  Conté el vídeo de demostració del projecte.

  - demo.mov:
      Vídeo de demo de l'IDSS.


Presentation/
  Conté la presentació final del projecte.

  - Presentation - Grup 8.pdf:
      Diapositives finals del grup.


README.txt
  Aquest fitxer. Resumeix què hi ha a cada carpeta i com executar la demo.

Dockerfile, docker-compose.yml, .dockerignore i .env.example
  Fitxers per executar l'IDSS dins d'un contenidor Docker sense dependre de
  l'entorn local de Python o Conda. El fitxer .env.example mostra les variables
  opcionals per activar l'enviament real de correus.


Com executar la demo de l'IDSS amb Docker
-----------------------------------------

Des d'aquesta carpeta d'entrega, executar:

  docker compose up --build

Quan el contenidor estigui actiu, obrir al navegador:

  http://localhost:8000/index.html
  http://localhost:8000/reserva_web.html

També es pot comprovar que l'API està activa amb:

  http://localhost:8000/api/health

El contenidor serveix tant el dashboard principal com la pàgina de reserva i
els endpoints de l'API. Per tant, no cal executar per separat index.html,
reserva_web.html ni el backend local.


Configuració opcional per enviar correus
----------------------------------------

El dashboard i la pàgina de reserva es poden executar sense configurar cap clau
ni credencial addicional. Si no s'afegeixen aquestes dades, la demo visual i la
part principal de l'IDSS continuen funcionant; simplement no es podran enviar
correus reals des de l'agent de correu.

Per activar l'enviament de correus, es poden definir aquestes variables d'entorn
abans d'executar Docker, o copiar .env.example a un fitxer .env al costat de
docker-compose.yml i omplir els valors necessaris:

  OPENAI_API_KEY=...
  OPENAI_MODEL_NAME=gpt-4o-mini
  EMAIL_ADDRESS=...
  EMAIL_PASSWORD=...
  EMAIL_HOST=smtp.gmail.com
  EMAIL_PORT=465

OPENAI_API_KEY s'utilitza per generar el text dels correus d'alt risc.
EMAIL_ADDRESS i EMAIL_PASSWORD s'utilitzen per enviar el correu via SMTP.


Notes finals
------------

- Els fitxers de dades originals i preprocessades es troben a Data/.
- Els models entrenats i els resultats d'interpretabilitat es troben a Models/.
- El codi font del sistema final es troba a IDSS/Interficie/.
- El codi de treball per reproduir preprocessament, entrenament i clustering es
  troba a Source/.
- Les regles expertes del sistema es troben a KnowledgeSources/ i també dins de
  la carpeta de la interfície perquè l'IDSS les pugui carregar localment.
