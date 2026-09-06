# Escopo

## Funcionalidade 01 - Pipeline de extração
Essa funcionalidade tem como objetivo receber um conjunto de textos e um esquema com as propriedades que devem ser extraídas. É uma boa candidata para SDD pois possui regras de negócios que envolvem o tratamento da entrada e construção da pipeline para a extração confiável dos dados. Possui casos de borda quando não há textos para serem processados e quando a quantidade de texto excede o limite aceitável para execução.

## Funcionalidade 02 - Store de modelos
Essa funcionalidade tem como objetivo realizar um controle dos modelos que estão disponíveis para extração. É uma boa candidata para SDD pois possui regras de negócios que envolvem o controle de versionamento e pipelines para inferência. Além disso, possui como casos de borda o versionamento de modelos vazios ou que excedem um limite de tamanho permitido. 
