# Resultados de T14 · Pruebas de permisos y de lecturas falsas

Ejecución del 12/11/2026 a las 17:58 (versión `73edadd`). Archivos: `tests/test_permisos_por_area.py` y `tests/test_lecturas_falsas.py`.

| | Casos | Pasan | Fallan |
|---|---|---|---|
| Intentos de ver datos de otra área o de otro rol (P01 a P40) | 40 | 40 | 0 |
| Intentos de colar lecturas falsas (F01 a F30) | 30 | 30 | 0 |
| Comprobaciones generales (recuento, mensajes sin datos, auditoría) | 4 | 4 | 0 |

«Pasa» significa que el servidor respondió **lo que la tabla de permisos (T09, apartado 6.2 de la documentación) exige**. Los intentos prohibidos devuelven siempre el mismo 403, sin enseñar ningún dato, y cada uno queda anotado como `acceso_denegado` en el registro de auditoría.

## Permisos: quién pregunta, qué pide y qué debe contestar el servidor

| Caso | Intento | Petición | Debe responder | Resultado |
|---|---|---|---|---|
| P01 | Laura (A1) pide el histórico de PT-201, de otra área | `/lecturas/historico?tag=PT-201` | 403 · prohibido | pasa |
| P02 | Laura (A1) pide el histórico de ST-301, de otra área | `/lecturas/historico?tag=ST-301` | 403 · prohibido | pasa |
| P03 | Laura (A1) pide el histórico de PT-401, de otra área | `/lecturas/historico?tag=PT-401` | 403 · prohibido | pasa |
| P04 | Laura (A1) pide el histórico de TE-501, de otra área | `/lecturas/historico?tag=TE-501` | 403 · prohibido | pasa |
| P05 | Laura (A1) pide el histórico de TE-601, de otra área | `/lecturas/historico?tag=TE-601` | 403 · prohibido | pasa |
| P06 | Laura (A1) pide el histórico de ET-701, de otra área | `/lecturas/historico?tag=ET-701` | 403 · prohibido | pasa |
| P07 | Laura (A1) pide el histórico de RT-801, de otra área | `/lecturas/historico?tag=RT-801` | 403 · prohibido | pasa |
| P08 | Laura (A1) pide el histórico de NT-901, de otra área | `/lecturas/historico?tag=NT-901` | 403 · prohibido | pasa |
| P09 | Laura (A1) intenta exportar a CSV el histórico de PT-201 | `/lecturas/historico/csv?tag=PT-201` | 403 · prohibido | pasa |
| P10 | Laura (A1) intenta exportar a CSV el histórico de ST-301 | `/lecturas/historico/csv?tag=ST-301` | 403 · prohibido | pasa |
| P11 | Laura (A1) intenta exportar a CSV el histórico de PT-401 | `/lecturas/historico/csv?tag=PT-401` | 403 · prohibido | pasa |
| P12 | Laura (A1) intenta exportar a CSV el histórico de TE-501 | `/lecturas/historico/csv?tag=TE-501` | 403 · prohibido | pasa |
| P13 | Laura (A1) intenta exportar a CSV el histórico de TE-601 | `/lecturas/historico/csv?tag=TE-601` | 403 · prohibido | pasa |
| P14 | Laura (A1) intenta exportar a CSV el histórico de ET-701 | `/lecturas/historico/csv?tag=ET-701` | 403 · prohibido | pasa |
| P15 | Laura (A1) intenta exportar a CSV el histórico de RT-801 | `/lecturas/historico/csv?tag=RT-801` | 403 · prohibido | pasa |
| P16 | Laura (A1) intenta exportar a CSV el histórico de NT-901 | `/lecturas/historico/csv?tag=NT-901` | 403 · prohibido | pasa |
| P17 | Laura (A1) pide las lecturas en directo: solo llegan sensores de A1 | `/lecturas/ultimas` | 200 · lo recibe | pasa |
| P18 | Javier (A2) pide las lecturas en directo: solo llegan sensores de A2 | `/lecturas/ultimas` | 200 · lo recibe | pasa |
| P19 | Diego pide el histórico de FT-103: es de su área pero de Nuria | `/lecturas/historico?tag=FT-103` | 403 · prohibido | pasa |
| P20 | Diego pide el histórico de LT-104: es de su área pero de Nuria | `/lecturas/historico?tag=LT-104` | 403 · prohibido | pasa |
| P21 | Diego pide el histórico de PT-201, de otra área | `/lecturas/historico?tag=PT-201` | 403 · prohibido | pasa |
| P22 | Diego pide el histórico de NT-901, de la red OT | `/lecturas/historico?tag=NT-901` | 403 · prohibido | pasa |
| P23 | Diego intenta exportar CSV de TE-101, que sí es suyo: los técnicos no exportan | `/lecturas/historico/csv?tag=TE-101` | 403 · prohibido | pasa |
| P24 | Diego intenta ver el equipo de su supervisor | `/equipo` | 403 · prohibido | pasa |
| P25 | Diego intenta ver el inventario de sensores | `/sensores` | 403 · prohibido | pasa |
| P26 | Diego pide las lecturas en directo: solo sus 2 sensores | `/lecturas/ultimas` | 200 · lo recibe | pasa |
| P27 | Diego pide 8 días de histórico de TE-101: el máximo del técnico son 7 | `/lecturas/historico?tag=TE-101&horas=192` | 422 · petición no válida | pasa |
| P28 | Diego pide 7 días de histórico de TE-101 | `/lecturas/historico?tag=TE-101&horas=168` | 200 · lo recibe | pasa |
| P29 | Beatriz (auditora) pide las lecturas en directo: solo agregados por área, sin valores | `/lecturas/ultimas` | 200 · lo recibe | pasa |
| P30 | Beatriz intenta exportar CSV del histórico | `/lecturas/historico/csv?tag=TE-101` | 403 · prohibido | pasa |
| P31 | Beatriz intenta ver el equipo de un supervisor | `/equipo` | 403 · prohibido | pasa |
| P32 | Beatriz intenta ver las alarmas (el auditor las ve solo en informes) | `/alarmas` | 403 · prohibido | pasa |
| P33 | Beatriz pide el histórico de PT-201: lo recibe agregado | `/lecturas/historico?tag=PT-201` | 200 · lo recibe | pasa |
| P34 | Álvaro (administrador) pide las lecturas en directo | `/lecturas/ultimas` | 403 · prohibido | pasa |
| P35 | Álvaro pide el histórico de TE-101 | `/lecturas/historico?tag=TE-101` | 403 · prohibido | pasa |
| P36 | Álvaro pide las alarmas | `/alarmas` | 403 · prohibido | pasa |
| P37 | Álvaro pide el equipo de un supervisor | `/equipo` | 403 · prohibido | pasa |
| P38 | Sin ninguna sesión se piden las lecturas en directo | `/lecturas/ultimas` | 401 · sin sesión | pasa |
| P39 | Con un token inventado se pide un histórico | `/lecturas/historico?tag=TE-101` | 401 · sin sesión | pasa |
| P40 | Javier (A2) pide su equipo: aparece Iván y no los técnicos de Laura | `/equipo` | 200 · lo recibe | pasa |

## Lecturas falsas: todo lo que debe rechazarse

En todos los casos, el servidor responde 401 (la firma no vale) o 422 (los datos no valen), **no guarda nada** y, si lo que falla son los datos, deja anotado el rechazo en la auditoría. Salvo F22 y F27, que comprueban que lo repetido no se pisa y que en un envío mezclado solo se guarda lo válido.

| Caso | Intento | Resultado |
|---|---|---|
| F01 | Envio sin firma | pasa |
| F02 | Firma hecha con otra clave | pasa |
| F03 | Valor alterado despues de firmar | pasa |
| F04 | Lectura anadida despues de firmar | pasa |
| F05 | Reenvio de un envio antiguo | pasa |
| F06 | Marca de tiempo del futuro | pasa |
| F07 | Firma en mayusculas | pasa |
| F08 | Firma cortada | pasa |
| F09 | Marca que no es un numero | pasa |
| F10 | Una sesion de supervisor no sirve para mandar lecturas | pasa |
| F11 | Valor por encima del maximo fisico | pasa |
| F12 | Valor por debajo del minimo fisico | pasa |
| F13 | Valor nan | pasa |
| F14 | Valor infinito | pasa |
| F15 | Valor escrito como texto con coma | pasa |
| F16 | Valor nulo | pasa |
| F17 | Sensor que no existe | pasa |
| F18 | Inyeccion sql en el tag | pasa |
| F19 | Fecha en el futuro | pasa |
| F20 | Fecha de hace mas de un mes | pasa |
| F21 | Fecha mal formada | pasa |
| F22 | Repetir un instante con otro valor no pisa el original | pasa |
| F23 | Envio de 501 lecturas | pasa |
| F24 | Envio vacio | pasa |
| F25 | Cuerpo que no es json | pasa |
| F26 | Sensor desactivado | pasa |
| F27 | En un envio mezclado solo se guarda lo valido y se anota lo demas | pasa |
| F28 | Una lectura falsa no abre alarmas | pasa |
| F29 | El limite justo del sensor se acepta y un poco mas no | pasa |
| F30 | Una firma buena no vale para el mismo cuerpo con un espacio de mas | pasa |

## Comprobaciones generales

| Prueba | Resultado |
|---|---|
| test_cada_intento_prohibido_queda_en_el_registro_de_auditoria | pasa |
| test_hay_exactamente_30_casos_con_su_numero | pasa |
| test_hay_exactamente_40_casos_con_su_numero | pasa |
| test_las_respuestas_prohibidas_no_enseñan_ningun_dato | pasa |
