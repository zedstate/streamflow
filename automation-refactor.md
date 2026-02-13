Agent prerequisites:
- Do not create specific MarkDown doc files for that specific feature, always try to incorporate it to existing documentation unless it is worth creating a separate document.
- Make sure that the repo is clean and sorted out after every implementation. Without redundant/unused code.
- Always perform code review (CodeQL), testing and linting. Keep the code standard-compliant.
- Check that all test related files are in their own directory. Everything must be well organized.
- Keep the documentation up to date.
- Configuration options introduced in code should be available in the UI as well.
- New UI components might require backend additions to support them.
- All API calls to Dispatcharr should be made via the UDI. If any changes should be made to the data models or anything related to Dispatcharr communication, refer to the swagger.json file for guidance on how to use the Dispatcharr API.
- For all UI changes, use ShadCN components and the ShadCN MCP. Take full advantage of the components to make every step of the experience modern and beautiful yet clean.

Before doing anything of the following prepare a develpment setup so we can build the docker image easily and deploy it. Make it sure to include it in the gitignore so we don't push this environment to the repo. Even if the explanation is in spanish, the contents of the code and the application should be in english.


Refactoring of the Automation System.
---
Idea General:

El proceso que ejecuta todo, es la Automation Run. La idea es programar una serie de eventos cada vez que pase esto.
Para esto, deberíamos poder asignar Automation Profiles. Estos perfiles se deberán poder asignar a canales o grupos de canales.
Dentro de cada Automation Profile debemos poder asignar que acciones queremos realizar:
1. M3U Update: Elegir qué playlists queremos actualizar
2. Stream Matching: Sí -> Utiliza las reglas de regex ya establecidas para añadir los streams al canal. No -> No realizar operación de añadir 
3. Stream Checking: No -> No se realiza ningún tipo de checkeo.
                    Sí, opciones: Con/Sin tiempo de gracia para los streams.
                                  Intentar revivir streams muertos.
                                  Límite de Streams en el canal: solo los "x" mejores streams se quedan en el canal
                                  Estadísticas necesarias: solo los streams con "x" resolución, "y" fps, "z" bitrate... Importante poder establecer regla mayor que, menor que o igual que.
                                  Ponderación de la puntuación personalizada para cada perfil.
                                  Prioridad de M3U Accounts: Mover sistema de prioridad para que se pueda personalizar separadamente en cada perfil.

4. Global Action: Elige si el canal es afectado por la run Global Action.
---
Consideraciones:
- La ejecución de un Automation Run: 
  - Se ejecutan primero todas las M3U updates de todos los perfiles, teniendo en cuenta que es importante no actualizar más de una vez cada playlist por cada run.
  - Luego se realizan, utilizando distintos workers (ya implementado), los procesos de matching de cada canal (si su automation profile así lo indica).
  - Por último, se realizan los checkeos de cada canal cumpliendo las opciones indicadas en su Automation Profile.
---
Cambios a la interfaz:
- Cambio de nombre de "Automation Settings" a "Settings".
- Dentro de "Settings", existe la sección "Automation". En la parte superior, deben de haber dos switches: Regular Automation (Activa o desactiva la Automation Run) y Global Action (Activa o desactiva la global action). Debajo, deben aparecer los Automation Profiles, siendo bloques seleccionables en grupo y eliminables. También debe de haber un botón de añadir.
- Al crear/editar un Automation Profile, se pasa al Automation Profile Studio. En este, se debe poder habilitar/deshabilitar/customizar las opciones mencionadas arriba. Al igual que cambiar el nombre del perfil y la descripción.
- En "Channel Configuration", deben de al igual que con las reglas de regex, haber opciones para agregar o quitar Automation Profiles de los canales tanto individualmente como en grupo. 
- En "Group Management" deben eliminarse las opciones de configurar "Stream Matching" y "Stream Checking" y ofrecer la opción de establecer el Automation Profile. Al igual que con las opciones actuales, si a un canal de un grupo se le ha puesto manualmente un Automation Profile, cambiar las opciones de su grupo no debería modificarlo.
  