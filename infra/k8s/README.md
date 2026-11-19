# Manifiestos de Kubernetes — MS-Notificaciones, MS-Reportes, DB-Reportes y RabbitMQ

Este directorio contiene los manifiestos declarativos de Kubernetes para el despliegue de la infraestructura de mensajería, bases de datos y microservicios reactivos en un clúster de Kubernetes (Minikube, K3s, EKS, GKE, etc.).

## Componentes Incluidos

| Servicio | Kind | Puertos Internos | Probes | Recursos (Req / Lim) |
|---|---|---|---|---|
| **rabbitmq** | Deployment + Service (ClusterIP) | 5672 (AMQP), 15672 (HTTP UI) | `rabbitmq-diagnostics -q ping` | 100m/256Mi - 500m/512Mi |
| **db-reportes** | Deployment + PVC + Service (ClusterIP) | 3306 (MySQL) | `mysqladmin ping` | 100m/256Mi - 500m/512Mi |
| **ms-notificaciones** | Deployment + Service (ClusterIP) | 5006 (HTTP) | HTTP GET `/health` (:5006) | 100m/128Mi - 300m/256Mi |
| **ms-reportes** | Deployment + Service (ClusterIP) | 5000 (HTTP) | HTTP GET `/health` (:5000) | 100m/128Mi - 500m/512Mi |

## Despliegue en el Clúster

Para aplicar todos los manifiestos:

```bash
kubectl apply -k infra/k8s/
# O individualmente:
kubectl apply -f infra/k8s/
```

Para verificar el estado de los pods y servicios:

```bash
kubectl get pods -l 'app in (rabbitmq, db-reportes, ms-notificaciones, ms-reportes)'
kubectl get svc -l 'app in (rabbitmq, db-reportes, ms-notificaciones, ms-reportes)'
```
