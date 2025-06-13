# redes2-p2p
# Proyecto P2P - Sistema de Compartición de Archivos

Este proyecto implementa un sistema de compartición de archivos basado en arquitectura P2P (Peer-to-Peer), con tres componentes principales: **Seeder**, **Leecher** y **Tracker**. Cada uno de estos componentes se comunica de manera eficiente siguiendo la arquitectura diseñada.

## Por qué usar Python

La elección de **Python** para este proyecto se basa en varias razones clave:

1. **Simplicidad y Legibilidad**: Python es conocido por su sintaxis sencilla y clara, lo que facilita el desarrollo rápido y la comprensión del código. Esto es crucial cuando el proyecto es desarrollado en equipo, ya que permite a todos los miembros trabajar de manera eficiente sin preocuparse por complejidades innecesarias del lenguaje.

2. **Bibliotecas y Herramientas Potentes**: Python cuenta con una amplia variedad de bibliotecas integradas y externas (como `asyncio`, `socket`, `requests`, `pytest`) que hacen que la implementación de funcionalidades complejas, como la comunicación en tiempo real entre nodos, la manipulación de archivos y las pruebas unitarias, sea mucho más sencilla.

3. **Desarrollo Rápido**: Python permite a los desarrolladores escribir menos código para lograr más funcionalidades. Esto es especialmente útil para proyectos donde el tiempo es limitado o en los que se planea hacer iteraciones rápidas durante el desarrollo.

4. **Compatibilidad y Flexibilidad**: Python es compatible con múltiples sistemas operativos (Linux, Windows, macOS) y tiene un ecosistema maduro para trabajar con redes, bases de datos y otras tecnologías clave en este tipo de proyectos. Esto asegura que el proyecto pueda ejecutarse sin problemas en diversos entornos.

5. **Comunidad Activa**: Python tiene una de las comunidades más grandes y activas, lo que facilita encontrar soluciones a problemas comunes y acceder a recursos educativos.

Aunque existen otras alternativas como **C/C++**, **Java** o **Go**, que podrían ser más rápidas en términos de rendimiento, **Python** ofrece una excelente combinación de facilidad de uso y poder para manejar las complejidades de un sistema distribuido como el proyecto P2P.


## Estructura del Proyecto

La comunicación entre los diferentes nodos sigue un flujo basado en el siguiente diseño:

- **Seeder**: Nodo que posee el archivo completo y lo divide en "chunks" (fragmentos). El Seeder está a la espera de solicitudes de los nodos Leecher para enviar los chunks disponibles.
- **Leecher**: Nodo que busca descargar un archivo completo, pero que solo tiene una parte de él. El Leecher solicita chunks al Seeder y los recibe a través del Tracker.
- **Tracker**: Nodo central que actúa como coordinador, gestionando las solicitudes de los nodos y su disponibilidad de chunks. El Tracker mantiene una base de datos de los nodos activos y los chunks disponibles.

## Flujo de Comunicación

1. **Seeder -> Tracker**: El Seeder se registra periódicamente en el Tracker, anunciando su disponibilidad y la lista de chunks que posee.
2. **Tracker -> Leecher**: El Leecher se conecta al Tracker y solicita la lista de chunks disponibles de los Seeds activos.
3. **Leecher -> Seeder**: El Leecher solicita chunks específicos a los Seeders, que se los envían a través de un protocolo de comunicación basado en sockets TCP/UDP.

## Requisitos

Para ejecutar este proyecto, necesitas tener instalado **Python 3.x** o superior y las siguientes dependencias. A continuación se presentan algunas posibles dependencias que podrías necesitar, aunque pueden variar según el avance y la implementación de cada parte del proyecto.

### Dependencias Posibles

- **socket**: Utilizado para la comunicación entre los nodos (Seeder, Leecher, Tracker) a través de TCP/UDP.
- **asyncio**: Para manejar múltiples conexiones simultáneas de manera eficiente.
- **threading**: Alternativa a `asyncio` para gestionar hilos y conexiones concurrentes.
- **requests**: Si necesitas hacer peticiones HTTP, por ejemplo, en el Tracker o en algún servicio relacionado.
- **pytest**: Para realizar pruebas unitarias y asegurar la correcta implementación de cada componente.

Puedes instalar las dependencias necesarias utilizando `pip`:

```bash
pip install socket asyncio threading requests pytest

