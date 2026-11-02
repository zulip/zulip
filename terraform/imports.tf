# El Deployment de Zulip existe en el clúster pero no en el estado,
# así que el apply intentaba crearlo de nuevo. Este bloque lo adopta
# en el próximo apply; después se puede borrar.
import {
  to = module.zulip.kubernetes_deployment_v1.this
  id = "zulip/zulip"
}
