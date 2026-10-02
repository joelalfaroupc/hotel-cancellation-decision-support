# Dashboard IDSS Hotelero

Este proyecto contiene una interfaz local y un motor IDSS para prevenir cancelaciones hoteleras. Ya no funciona solo como visualizador: recalcula probabilidad de cancelacion, asigna perfil TLP y genera acciones a partir de reglas de negocio.

## Que hace ahora

- Carga `best_model.joblib` y usa XGBoost para calcular `P(cancelacion)`.
- Usa `hotel_clustering_output.csv` para asignar cada reserva a un cluster/perfil TLP mediante distancia a centroides.
- Lee `reglas_negocio_idss_experto.yaml` para decidir canales, timing y acciones a partir del score ML, el cluster y el perfil TLP.
- Cruza `dataset_5000.csv` para recuperar datos base como pais real de la reserva y `deposit_type`.
- Genera `dashboard_data.js`, que alimenta el dashboard en el navegador.
- Carga de inicio una muestra operativa de 20 reservas, con 5 por nivel de riesgo.
- Permite simular una nueva reserva desde la interfaz, incluyendo tipo de deposito, y obtener probabilidad, perfil y plan de actuacion.
- Permite enviar un email real al huesped para reservas nuevas de riesgo ALTO o CRITICO cuando el canal recomendado incluye email.

La decision operativa se apoya en la probabilidad de cancelacion producida por el modelo, en el segmento obtenido por clustering y en la interpretacion de ese segmento mediante profiling TLP. Las reglas explican por que se recomienda una actuacion desde una perspectiva operativa, no como atribucion causal de variables.

`deposit_type` se mantiene como dato contextual visible en la interfaz, pero no entra en el modelo ML ni activa reglas adicionales. El score de cancelacion se calcula sin usar esta variable y las acciones salen del perfil TLP asignado por clustering combinado con el nivel de riesgo.

## Estado actual de las acciones

Las acciones recomendadas estan centralizadas en `reglas_negocio_idss_experto.yaml`:

- cada perfil TLP tiene acciones base por nivel de riesgo (`BAJO`, `MEDIO`, `ALTO`, `CRITICO`);
- cada cluster documenta su descripcion operativa, variables distintivas y logica de negocio;
- `reglas_globales` queda vacio por compatibilidad con la interfaz, pero no se usa para generar acciones.

El motor Python (`idss_engine.py`) y el simulador del navegador (`app.js`) siguen la misma idea: asignan el perfil TLP desde el cluster, calculan el nivel de riesgo y cargan las acciones del bloque perfil/riesgo. `dashboard_data.js` guarda el resultado ya materializado para las reservas visibles en el dashboard.

La implementacion actual limita la lista visible a un plan de actuacion consolidado para que cada reserva tenga pocas opciones accionables y justificadas por su perfil.

## Flujo IDSS

1. Reserva nueva o existente.
2. XGBoost calcula probabilidad de cancelacion.
3. El motor TLP asigna cluster y perfil operativo.
4. Las reglas YAML combinan el nivel de riesgo derivado del score ML con el perfil TLP asignado por clustering.
5. El dashboard muestra una cartera inicial reducida y ordena reservas por urgencia de tratamiento.
6. El usuario puede preparar llamada, email, SMS, garantia o marcar la accion realizada.

## Siguiente modificacion prevista

El siguiente cambio que se quiere abordar es mejorar la capa de acciones recomendadas. La direccion acordada es no seguir ampliando listas de texto libre, sino estructurar las acciones para que el motor pueda priorizarlas, deduplicarlas y mostrar solo las mas utiles.

Propuesta de estructura futura para cada accion:

- `tipo`: confirmacion, comunicacion, garantia, flexibilidad, revenue, CRM, incentivo o revision manual;
- `prioridad`: accion principal, accion secundaria o seguimiento opcional;
- `canal`: email, SMS, llamada, manual, revenue o direccion;
- `coste_operativo`: bajo, medio o alto;
- `accion`: instruccion concreta que vera el usuario;
- `motivo`: explicacion breve basada en score ML y perfil TLP;
- `condiciones`: perfil TLP y nivel de riesgo que activan la accion.

Objetivo operativo:

- devolver una accion principal por reserva;
- devolver como maximo dos acciones secundarias;
- dejar una accion opcional de seguimiento si aporta valor;
- evitar acciones repetidas, contradictorias o demasiado genericas;
- mantener `deposit_type` solo como contexto visible, nunca como feature ML ni como regla paralela.

## Archivos principales

- `index.html`: estructura visual del dashboard.
- `styles.css`: paleta, layout, calendario, tabla, ficha y formulario de nueva reserva.
- `app.js`: interaccion del dashboard, calendario, ficha de reserva y simulador en navegador.
- `dashboard_data.js`: datos generados para abrir el dashboard sin servidor.
- `idss_engine.py`: motor real del IDSS con XGBoost, clustering TLP y reglas YAML.
- `generate_dashboard_data.py`: script que ejecuta el motor y regenera `dashboard_data.js`.
- `email_agent/`: API local FastAPI, generacion de email con OpenAI y envio SMTP.
- `requirements-agent.txt`: dependencias del backend local de email.
- `README_DASHBOARD_IDSS.md`: este documento.

## Agente de email local

El envio real de emails requiere ejecutar el backend local FastAPI. El mismo agente cubre dos casos:

- emails operativos desde el dashboard para reservas nuevas de riesgo `ALTO` o `CRITICO`;
- emails automaticos de confirmacion cuando un cliente completa una reserva en `reserva_web.html`.

La confirmacion de reserva **no usa OpenAI ni ChatGPT**: genera un texto fijo con los datos de la reserva y lo envia con el mismo `SMTPMailSender` que ya usa el agente de email. La parte de OpenAI queda solo para la redaccion asistida de emails operativos del dashboard, si se configura.

Instalar dependencias desde `IDSS_Hotels/Interficie`:

```bash
conda run -n paid python -m pip install -r requirements-agent.txt
```

Crear un `.env` local no versionado a partir de `.env.example` y configurar como minimo el SMTP:

```bash
EMAIL_ADDRESS=hotel@example.com
EMAIL_PASSWORD=app-password-or-smtp-password
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=465
```

Si se usa Gmail, `EMAIL_PASSWORD` debe ser una App Password, no la contrasena normal de la cuenta. `OPENAI_API_KEY` solo es necesario si se quiere usar la generacion asistida del email operativo del dashboard.

Arrancar la web publica y el dashboard con API desde `IDSS_Hotels/Interficie`:

```bash
conda run -n paid python -m uvicorn email_agent.api:app --reload --port 8000
```

Abrir la web publica en `http://127.0.0.1:8000/reserva_web.html`. Al confirmar una reserva, la pagina llama a `POST /api/booking-confirmation-email` y el backend envia el correo desde `EMAIL_ADDRESS`. Si se abre con un servidor estatico, la reserva se registra localmente, pero no existe el endpoint de email.

El dashboard interno queda disponible en `http://127.0.0.1:8000/index.html`. El boton `Enviar email` del dashboard solo envia si la reserva tiene email de huesped y riesgo `ALTO` o `CRITICO`. Las reservas historicas no incluyen email, por lo que el envio real esta pensado para reservas creadas desde la web publica o desde el formulario `Nueva reserva`.

## Datos fuente usados

El dashboard se regenera con rutas relativas al repositorio clonado:

- `Interficie/model_artifacts/best_model.joblib`: modelo XGBoost actual.
- `Interficie/model_artifacts/best_model_summary.json`: resumen del modelo actual, con 65 variables procesadas.
- `Interficie/model_artifacts/leaderboard.csv`: comparativa de modelos actual.
- `Interficie/hotel_clustering_output.csv`: salida actual del pipeline de clustering con cluster/perfil TLP.
- `Interficie/dataset_5000.csv`: dataset original usado para recuperar datos base como pais y `deposit_type`.
- `Interficie/reglas_negocio_idss_experto.yaml`: reglas operativas derivadas de los perfiles TLP del clustering.

El modelo usado por la interfaz corresponde al pipeline nuevo: `arrival_date_year` se trata como categorica y aparece como `cat__arrival_date_year_2015`, `cat__arrival_date_year_2016` y `cat__arrival_date_year_2017`. `deposit_type` no forma parte del modelo actual ni debe introducirse en la matriz ML; se conserva aparte como informacion contextual.

## Como regenerar el dashboard

Desde la raiz del repositorio:

```bash
conda run -n paid python Interficie/generate_dashboard_data.py
```

Dependencias minimas del motor de interfaz:

```bash
conda run -n paid python -m pip install -r Interficie/requirements.txt
```

Ese comando vuelve a calcular las reservas con el motor y sobrescribe `dashboard_data.js`.

## Que modificar

Para cambiar reglas de decision:

- Editar `Interficie/reglas_negocio_idss_experto.yaml`.
- Volver a ejecutar `generate_dashboard_data.py`.
- Refrescar `index.html`.
- Mantener las reglas alineadas con los perfiles TLP del clustering para no mezclar criterios externos.

Para cambiar reservas base:

- Editar o sustituir `Interficie/hotel_clustering_output.csv`.
- Si cambian paises u otras variables originales, editar tambien `Interficie/dataset_5000.csv`.
- Regenerar `dashboard_data.js`.

Para cambiar el modelo:

- Sustituir `Interficie/model_artifacts/best_model.joblib`.
- Mantener las mismas columnas esperadas por el modelo o adaptar `idss_engine.py`.
- Regenerar `dashboard_data.js`.

Para cambiar la interfaz:

- Textos y estructura: `index.html`.
- Estilos y colores: `styles.css`.
- Logica de interaccion y explicaciones: `app.js`.
- Motor de decision real: `idss_engine.py`.

## Que enviar a companeros

Para que solo abran y revisen el dashboard:

- `index.html`
- `styles.css`
- `app.js`
- `dashboard_data.js`
- `README_DASHBOARD_IDSS.md`

Para que puedan modificar reglas y regenerar datos:

- Todo lo anterior.
- `idss_engine.py`
- `generate_dashboard_data.py`
- `reglas_negocio_idss_experto.yaml`
- `hotel_clustering_output.csv`
- `dataset_5000.csv`
- `best_model.joblib`

Para reproducir el proyecto completo:

- Tambien enviar notebooks (`idss_hotelero.ipynb`, clustering, entrenamiento) y datasets auxiliares (`clustering_dataset.csv`, etc.).

## Nota

El dashboard local simula la mayor parte de la ejecucion operativa: no llama, no envia SMS y no modifica PMS/CRM. El envio real de email solo funciona si se arranca el backend `email_agent` con credenciales configuradas; sin ese backend, los botones preparan o programan acciones dentro de la interfaz.
