# Fundamentação Técnica do Projeto — Cálculo de Distâncias entre Códigos Postais
## 1. Objetivo do Projeto
O objetivo principal deste projeto é calcular de forma o mais precisa possível a distância e o tempo estimado de deslocação entre dois códigos postais, considerando diferentes meios de transporte (camião, automóvel, bicicleta, a pé, etc.).
Para isso, é utilizada uma combinação de APIs geográficas que permitem obter as coordenadas e efetuar o cálculo das rotas.
 
## 2. Arquitetura Geral da Solução
Fluxo de funcionamento:
1.	São fornecidos os códigos postais de origem e destino
2.	O sistema consulta uma API para obter as coordenadas (latitude e longitude) de cada código postal.
3.	Caso a API devolva múltiplas coordenadas para o mesmo código postal, é calculada a média aritmética de todas as coordenadas retornadas (centroide).
4.	De posse das coordenadas médias da origem e do destino, o sistema invoca a API da TomTom Routing para:
    -	Calcular a distância entre os dois pontos;
    -	Obter o tempo estimado de percurso;
    -	Considerar o modo de transporte (camião, carro, bicicleta, a pé, etc.).
5.	Os resultados são devolvidos neste momento em ficheiro Excel.

## 3. Componentes Técnicos
### 3.1. API de Geocodificação (Obtenção de Coordenadas)
-	Função: Converter um código postal em coordenadas geográficas (latitude, longitude).
-	Exemplos de APIs utilizadas:
    - codigo-postal.pt

Processamento adicional:
-	Em alguns casos, o mesmo código postal pode corresponder a várias localizações.
-	Para uniformizar o cálculo, é calculada a média das latitudes e média das longitudes, obtendo um ponto central representativo desse código postal.

### 3.2. API da TomTom (Cálculo de Distância e Tempo)
-	Função: Calcular a rota entre dois pontos GPS, considerando o modo de transporte.
-	Endpoint típico: https://api.tomtom.com/routing/1/calculateRoute/{origem}:{destino}/json?travelMode={modo}&key={API_KEY}
-	Principais parâmetros:
  -	origem e destino: coordenadas GPS médias obtidas na etapa anterior;
  -	travelMode: define o tipo de transporte (car, pedestrian, bicycle, truck, etc.);
  -	traffic: opcional, para incluir tempo real de trânsito.
-	Principais resultados retornados:
  -	Distância total (em metros ou km);
  -	Tempo estimado de viagem;
  -	Itinerário e passos de navegação (opcional).
 
## 4. Resultados Esperados
-	Distância total (km ou metros);
-	Tempo estimado de deslocação (segundos ou minutos);
 
## 5. Vantagens da Solução
-	Automação total do processo de cálculo;
-	Flexibilidade — pode ser adaptada a diferentes países e tipos de transporte;
-	Futura integração com a logística por exemplo para planeamento de transportes.
