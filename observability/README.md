# /observability

Manifiestos de configuración de monitoreo del Entregable 3 (SLIs/SLOs/Error Budget/Alertamiento). Se
provisionan dentro del clúster vía Terraform (`terraform/modules/monitoring/main.tf`), que solo inyecta
estos archivos en ConfigMaps sin interpretarlos — la lectura/validación real la hace Grafana en tiempo de
arranque (provisioning nativo).

## Contenido

- `dashboards/zulip-slo.json` — dashboard de Grafana "Zulip · SLI y SLO de mensajería": disponibilidad de
  `POST /messages` (SLO 99%), presupuesto de error y burn rate, latencia de entrega p95 (SLO ≤2.5s), y
  estado de los exporters/componentes con estado (Postgres, Redis).
- `alerting/rules/` — reglas de alerta de **Burn Rate Alerting** (formato de provisioning nativo de
  Grafana, `apiVersion: 1`), una por escenario de simulación cubierto:
  - `availability-burn-rate.yaml` — Escenario A (caída de RabbitMQ → rompe el SLO de disponibilidad).
  - `latency-burn-rate.yaml` — Escenario C (degradación de RabbitMQ → rompe el SLO de latencia).
- `alerting/contactpoints.yaml` — contact point de email para las notificaciones.
- `alerting/notification-policies.yaml` — política de enrutamiento de las alertas hacia ese contact point.

## Alcance

De los 4 escenarios de simulación diseñados (ver `ESCENARIOS_SIMULACION_ALERTAMIENTO.md`), solo **A** y
**C** tienen regla de alerta por ahora — **B** (caída de Postgres) y **D** (saturación por volumen) quedan
fuera de alcance de esta entrega por tiempo.

## Por qué Grafana Alerting y no Cloud Monitoring

Se evaluó usar `google_monitoring_alert_policy` (Cloud Monitoring), pero se descartó: (1) requiere un
permiso IAM (`roles/monitoring.*`) que hoy falta en la cuenta de servicio del pipeline y cuyo arreglo vive
en un Terraform state separado (`terraform/bootstrap`) fuera del flujo normal de CI/CD; (2) el enunciado
del curso nombra explícitamente "Prometheus y Grafana" como la pila esperada, no Cloud Monitoring. Grafana
Alerting reutiliza la infraestructura ya desplegada, sin permisos nuevos, y mantiene todo dentro de la
pila Prometheus/Grafana pedida.

## Umbral de burn rate

Ambas reglas usan el mismo patrón: `(métrica observada en la ventana de 1h) / (margen del SLO) > 5`. El
multiplicador 5 corresponde a un horizonte de agotamiento del presupuesto de 30 días en ~6 días si la tasa
de fallos se sostiene — ver la justificación completa en `RESUMEN_AVANCE_SLI_SLO_ERROR_BUDGET.md`.

## Verificación pendiente antes de dar esto por definitivo

El esquema exacto de provisioning de Grafana Alerting (campos de `data`/`condition`/`model`) se escribió
siguiendo la documentación oficial de Grafana, pero no se validó corriendo un Grafana real en este entorno
(sin acceso a él desde aquí). **Antes de confiar en esto para la entrega, cárgalo en el Grafana real del
proyecto** (ver instructivo de acceso compartido por el equipo) y confirma en la UI, bajo Alerting → Alert
rules, que ambas reglas aparecen sin errores de parseo.
