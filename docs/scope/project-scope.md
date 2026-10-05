# Alcance del proyecto

El proyecto se enfocará en implementar la mejora propuesta en el issue #7719 de Zulip, relacionada con la notificación de usuarios mencionados que no están suscritos a un canal.

La funcionalidad permitirá que, cuando un usuario mencione a otra persona que no está suscrita al canal pero sí tiene permisos para acceder a él, se muestre una opción adicional para notificarla sin modificar su suscripción.

## Incluido en el alcance

- Menciones individuales en mensajes nuevos enviados desde la aplicación web.
- Modificación del aviso mostrado al mencionar a un usuario no suscrito.
- Incorporación de la opción «Notificar» junto a «Suscribir».
- Validación de permisos de acceso al canal.
- Generación de una notificación mediante Notification Bot.
- Inclusión de un enlace hacia la conversación y referencia al mensaje original.
- Conservación de la suscripción actual del usuario mencionado.
- Pruebas funcionales y automatizadas.
- Documentación técnica de la mejora.

## Fuera del alcance

- Cambios en clientes móviles.
- Menciones a grupos o menciones masivas.
- Notificaciones retroactivas al editar mensajes.
- Nuevas integraciones externas.
- Rediseños generales del sistema de notificaciones.
- Cambios en las reglas de acceso a canales.
- Notificación a usuarios que no tengan permisos para acceder al canal.

El proyecto se limita al flujo relacionado con menciones, permisos, suscripciones y notificaciones, sin modificar otras funcionalidades generales de Zulip.