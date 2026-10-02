# Estado y pendientes de la web publica de reservas

## 1) Estado actual

- La web publica `reserva_web.html` ya queda separada del dashboard: al finalizar la reserva no muestra boton ni enlace al panel interno del hotel.
- La confirmacion final se limita a indicar que la reserva se ha registrado y muestra el resumen de la estancia.
- El formulario publico pide los mismos datos operativos que necesita el flujo interno, incluyendo nombre, email y tipo de deposito.
- La conexion con el dashboard sigue siendo local mediante `localStorage`, de momento sin base de datos ni API persistente.

## 2) Email automatico de confirmacion

- La pagina publica llama a `POST /api/booking-confirmation-email` cuando el cliente confirma la reserva.
- Ese endpoint esta implementado dentro del mismo agente local de email que usa el dashboard.
- Para la confirmacion de reserva no se usa OpenAI/ChatGPT: se genera un texto fijo con los datos de la reserva y se envia directamente por SMTP.
- El correo sale desde la misma cuenta configurada para el agente de email mediante `EMAIL_ADDRESS`, `EMAIL_PASSWORD`, `EMAIL_HOST` y `EMAIL_PORT`.

Arranque recomendado desde `IDSS_Hotels/Interficie`:

```bash
conda run -n paid python -m uvicorn email_agent.api:app --reload --port 8000
```

Abrir despues:

```text
http://127.0.0.1:8000/reserva_web.html
```

Si se abre la pagina con un servidor estatico, la reserva se registra localmente, pero la llamada de email no puede completarse porque no existe el endpoint FastAPI.

## 3) Configuracion SMTP

Crear un archivo local `.env` a partir de `.env.example` y definir como minimo:

```bash
EMAIL_ADDRESS=...
EMAIL_PASSWORD=...
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=465
```

Si se usa Gmail, `EMAIL_PASSWORD` debe ser una **App Password**, no la contrasena normal. El archivo `.env` no debe subirse al repositorio.

## 4) Separacion funcional

- La web publica es la interfaz de clientes.
- El dashboard es la interfaz interna del hotel.
- Ahora la separacion se hace por paginas distintas dentro del mismo backend local.
- A futuro, si se despliega fuera de local, conviene publicar solo la ruta de reservas y proteger el dashboard interno con autenticacion o una red privada.

## 5) Verificacion pendiente con credenciales reales

Cuando haya SMTP configurado, probar con navegador real:

- abrir `http://127.0.0.1:8000/reserva_web.html`;
- hacer una reserva con email real;
- comprobar que la pantalla final no muestra acceso al dashboard;
- comprobar que el email llega con los datos de la reserva;
- comprobar que la reserva aparece en el dashboard al abrir `index.html` en el mismo navegador;
- revisar que no haya duplicados en `localStorage`.
