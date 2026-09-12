# 0005-uso-de-tdd-com-superpowers.md

## Contexto

O projeto precisa evoluir com segurança, preservando o comportamento esperado da extração de informações por LLM. Alterações sem uma validação automatizada prévia aumentam o risco de regressões. O conjunto de habilidades Superpowers oferece um fluxo de TDD que orienta a criação de testes antes da implementação.

## Decisão

Adotar TDD como prática padrão para novas funcionalidades e correções de defeitos, utilizando a habilidade `superpowers:test-driven-development`. A implementação seguirá o ciclo Red-Green-Refactor: escrever um teste que falha, implementar apenas o necessário para fazê-lo passar e refatorar mantendo os testes verdes.

## Consequências

Ganha-se maior confiança nas mudanças, especificações executáveis do comportamento esperado e detecção antecipada de regressões. Em contrapartida, o desenvolvimento inicial pode exigir mais tempo para definir cenários de teste e manter a suíte automatizada. Casos que dependam diretamente de modelos de linguagem devem privilegiar testes determinísticos com stubs ou mocks para evitar instabilidade e custo desnecessário.
