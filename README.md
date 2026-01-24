# E-commerce: Comparativo Sync vs Async

Sistema de e-commerce para comparar padroes de comunicacao **sincrona** (REST/HTTP) e **assincrona** (RabbitMQ/Eventos) em arquitetura de microsservicos.

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│  ┌──────────┐    ┌─────────────┐                                │
│  │    UI    │    │ API Gateway │                                │
│  │  :8501   │    │   :8181     │                                │
│  └────┬─────┘    └──────┬──────┘                                │
└───────┼─────────────────┼───────────────────────────────────────┘
        │                 │
┌───────┼─────────────────┼───────────────────────────────────────┐
│       │            BACKEND                                       │
│       │                 │                                        │
│  ┌────┴────┐    ┌──────┴──────┐    ┌──────────┐                 │
│  │ Catalog │    │    Order    │    │ Payment  │                 │
│  │  :8001  │    │    :8003    │    │  :8004   │                 │
│  └─────────┘    └──────┬──────┘    └──────────┘                 │
│                        │                                         │
│  ┌─────────┐    ┌──────┴──────┐    ┌──────────┐                 │
│  │  Cart   │    │  RabbitMQ   │    │Inventory │                 │
│  │  :8002  │    │ :5673/15692 │    │  :8005   │                 │
│  └─────────┘    └─────────────┘    └──────────┘                 │
└─────────────────────────────────────────────────────────────────┘
        │
┌───────┴─────────────────────────────────────────────────────────┐
│                    OBSERVABILIDADE                               │
│  ┌──────────┐  ┌──────────┐  ┌────────┐  ┌────────┐            │
│  │PostgreSQL│  │Prometheus│  │Grafana │  │ Jaeger │            │
│  │  :5432   │  │  :9090   │  │ :3000  │  │ :16686 │            │
│  └──────────┘  └──────────┘  └────────┘  └────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## Servicos

| Servico           | Porta      | Descricao                             |
| ----------------- | ---------- | ------------------------------------- |
| UI (Streamlit)    | 8501       | Interface web para compras            |
| API Gateway       | 8181       | Ponto de entrada da API               |
| Catalog Service   | 8001       | Gerenciamento de produtos             |
| Cart Service      | 8002       | Carrinho de compras                   |
| Order Service     | 8003       | Processamento de pedidos (sync/async) |
| Payment Service   | 8004       | Simulacao de pagamentos               |
| Inventory Service | 8005       | Controle de estoque                   |
| RabbitMQ          | 5673/15692 | Message broker                        |
| PostgreSQL        | 5433       | Banco de dados                        |
| Redis             | 6380       | Cache                                 |
| Prometheus        | 9090       | Metricas                              |
| Grafana           | 3000       | Dashboards                            |
| Jaeger            | 16686      | Distributed tracing                   |

## Requisitos

- Docker e Docker Compose
- Make (opcional, para comandos simplificados)
- 8GB RAM minimo recomendado

## Inicio Rapido

1. **Clone e configure:**

```bash
cd ecommerce-comparison
cp .env.example .env
```

2. **Inicie os servicos:**

```bash
make up
# ou
cd infra && docker-compose up -d
```

3. **Acesse:**

- UI: http://localhost:8501
- API Gateway: http://localhost:8181
- Grafana: http://localhost:3000 (admin/admin)
- RabbitMQ: http://localhost:15692 (guest/guest)
- Jaeger: http://localhost:16686

## Modos de Comunicacao

### Modo Sincrono (sync)

- Chamadas HTTP diretas entre servicos
- Fluxo: Order -> Payment -> Inventory
- Resposta imediata ao cliente
- Acoplamento temporal

### Modo Assincrono (async)

- Eventos via RabbitMQ
- Padrao Saga para orquestracao
- Resposta imediata com status "pending"
- Processamento em background
- Dead Letter Queues para falhas

**Fluxo de Eventos (Async):**

```
OrderCreated -> PaymentRequested -> PaymentSucceeded -> StockReserved -> OrderCompleted
                                 -> PaymentFailed ----------------------> OrderFailed
                                                     -> StockFailed ----> OrderFailed
```

## Comandos Make

```bash
# Infraestrutura
make up              # Inicia todos os servicos
make up-sync         # Inicia em modo sincrono
make up-async        # Inicia em modo assincrono
make down            # Para todos os servicos
make logs            # Ver logs
make status          # Ver status dos servicos
make clean           # Remove tudo (containers, volumes, imagens)

# Testes de Carga
make test-load-sync  # Teste de carga modo sync
make test-load-async # Teste de carga modo async
make locust          # Inicia UI do Locust

# Utilitarios
make db-shell        # Acessa shell do PostgreSQL
make seed            # Popula dados iniciais
```

## Testes de Carga

O Locust esta configurado para simular usuarios reais:

1. **Inicie o Locust:**

```bash
make locust
```

2. **Acesse:** http://localhost:8089

3. **Configure:**
   - Number of users: 50
   - Spawn rate: 5
   - Host: http://api-gateway:8181

**Usuarios simulados:**

- `EcommerceUser`: Usuario tipico (navegacao + compras)
- `SyncUser`: Apenas modo sincrono
- `AsyncUser`: Apenas modo assincrono
- `BrowseOnlyUser`: Apenas navegacao (leitura)
- `CheckoutHeavyUser`: Foco em checkout (escrita)

## Metricas

### Prometheus Queries

```promql
# Throughput por modo
sum(rate(http_requests_total{communication_mode="sync"}[1m]))
sum(rate(http_requests_total{communication_mode="async"}[1m]))

# Latencia P95
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, communication_mode))

# Taxa de erros
sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)

# Mensagens RabbitMQ
sum(rate(rabbitmq_messages_published_total[1m]))
sum(rate(rabbitmq_messages_consumed_total[1m]))
```

### Grafana Dashboard

Dashboard pre-configurado em: http://localhost:3000

Paineis:

- Throughput Sync vs Async
- Latencia (P50, P95, P99)
- Taxa de erros
- Metricas por servico
- Filas RabbitMQ

## Estrutura do Projeto

```
ecommerce-comparison/
├── services/
│   ├── api-gateway/      # Roteamento de requisicoes
│   ├── catalog-service/  # CRUD de produtos
│   ├── cart-service/     # Carrinho de compras
│   ├── order-service/    # Pedidos (sync + async handlers)
│   ├── payment-service/  # Pagamentos + worker async
│   ├── inventory-service/# Estoque + worker async
│   └── shared/           # Bibliotecas compartilhadas
├── infra/
│   ├── docker-compose.yml
│   ├── prometheus/
│   ├── grafana/
│   └── rabbitmq/
├── ui/                   # Interface Streamlit
├── tests/load/           # Testes Locust
├── scripts/              # Scripts de inicializacao
├── Makefile
└── README.md
```

## Decisoes Tecnicas

| Componente     | Escolha                | Justificativa                      |
| -------------- | ---------------------- | ---------------------------------- |
| Framework      | FastAPI                | Async nativo, performance, OpenAPI |
| UI             | Streamlit              | Python puro, rapido de desenvolver |
| Load Tests     | Locust                 | Python, boa integracao, relatorios |
| Message Broker | RabbitMQ               | Robusto, DLQ nativo, management UI |
| Tracing        | Jaeger + OpenTelemetry | Padrao de mercado                  |
| Metricas       | Prometheus + Grafana   | Stack consagrado                   |
| ORM            | SQLAlchemy (async)     | Suporte asyncio nativo             |

## Padrao Saga

O servico de pedidos implementa o padrao Saga para o modo assincrono:

1. **Criacao do Pedido** - Estado inicial
2. **Pagamento** - Publica `payment.requested`
3. **Pagamento OK** - Recebe `payment.succeeded`, publica `stock.reserve`
4. **Estoque OK** - Recebe `stock.reserved`, publica `order.completed`
5. **Falha** - Compensacoes automaticas

Estados da Saga:

- `created` - Pedido criado
- `payment_requested` - Aguardando pagamento
- `payment_completed` - Pagamento OK
- `stock_requested` - Aguardando reserva
- `completed` - Finalizado
- `failed` - Falhou
- `compensating` - Executando rollback

## Configuracao

### Variaveis de Ambiente (.env)

```env
# Banco de Dados
DATABASE_URL=postgresql://ecommerce:ecommerce_pass@postgres:5432/ecommerce

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/

# Modo de Comunicacao
COMMUNICATION_MODE=sync  # sync ou async

# Simulacao de Pagamento
PAYMENT_FAILURE_RATE=0.1  # 10% de falha
PAYMENT_DELAY_MS=100      # 100ms de delay
```

## Troubleshooting

### Servicos nao iniciam

```bash
make logs
docker-compose ps
```

### Banco de dados vazio

```bash
make seed
```

### RabbitMQ sem filas

As filas sao criadas automaticamente pelo `definitions.json`. Verifique em http://localhost:15692.

### Prometheus sem metricas

Aguarde alguns minutos para scraping. Verifique targets em http://localhost:9090/targets.

## Proximos Passos

- [ ] Adicionar Circuit Breaker com Resilience4j
- [ ] Implementar retry com backoff exponencial
- [ ] Adicionar rate limiting
- [ ] Implementar cache distribuido
- [ ] Adicionar autenticacao JWT
- [ ] Kubernetes deployment

## Licenca

Projeto academico para TCC - MBA Engenharia de Software USP/Esalq.

---

Desenvolvido por Vitor Silva - 2024
