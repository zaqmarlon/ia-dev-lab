# Entity Extraction API

Uma API HTTP simples para extração de entidades de texto. No estado atual, a extração é simulada com uma resposta fixa, servindo como base para a futura integração com um modelo de linguagem.

## Requisitos

- Python 3.9 ou superior

O projeto usa apenas a biblioteca padrão do Python.

## Testes

Execute a suíte de testes a partir da raiz do repositório:

```bash
python -m unittest discover -s tests
```

## Endpoints

| Método | Rota | Resposta |
| --- | --- | --- |
| `GET` | `/ping` | Verifica a disponibilidade da aplicação. |
| `POST` | `/entities` | Retorna as entidades extraídas do texto enviado. |

### `GET /ping`

Resposta de sucesso:

```json
{
  "message": "pong"
}
```

### `POST /entities`

Envie um JSON com o campo `text`:

```json
{
  "text": "OpenAI is based in San Francisco."
}
```

Resposta atual:

```json
{
  "entities": [
    {
      "text": "OpenAI",
      "label": "ORG",
      "confidence": 0.98
    },
    {
      "text": "San Francisco",
      "label": "GPE",
      "confidence": 0.95
    }
  ]
}
```

## Estrutura

```text
src/
  app.py       Manipulador HTTP e rotas
  service.py   Serviço de extração simulado
  schemas.py   Tipos de dados da API
tests/         Testes dos endpoints
docs/adr/      Decisões de arquitetura
```

## Próximos passos

Substituir o serviço simulado por uma integração com LLM e disponibilizar um ponto de entrada para executar o servidor HTTP.
