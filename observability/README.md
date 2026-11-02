# MANIFIESTO DE OBSERVABILIDAD

GRUPO A:
- Fabian Camilo Castro Lozano
- Jorge Orlando Celemin Rodriguez
- Kelly Johana Solano Calderón


---

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
  - `availability-burn-rate.yaml` — escenario de disponibilidad (caída de RabbitMQ → rompe el SLO de disponibilidad).
  - `latency-burn-rate.yaml` — escenario de latencia (degradación de RabbitMQ → rompe el SLO de latencia).
- `alerting/contactpoints.yaml` — contact point de email para las notificaciones.
- `alerting/notification-policies.yaml` — política de enrutamiento de las alertas hacia ese contact point.

## Alcance

Por ahora solo existen reglas de alerta para el escenario de **disponibilidad** y el de **latencia**
(ambos centrados en una caída/degradación de RabbitMQ) — otros escenarios de degradación (por ejemplo,
caída de la base de datos o saturación por volumen de tráfico) quedan fuera de alcance de esta entrega.

## Umbral de burn rate

Ambas reglas usan el mismo patrón: `(métrica observada en la ventana de 1h) / (margen del SLO) > 5`. El
multiplicador 5 corresponde a un horizonte de agotamiento del presupuesto de 30 días en ~6 días si la tasa
de fallos se sostiene.
