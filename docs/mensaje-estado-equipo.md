# Mensaje de estado para el equipo

Fecha: 2026-09-11. Para copiar y pegar en chat o correo. Se puede enviar todo junto o en dos
partes: primero el estado, después el detalle de herramientas y flujo.

---

## Parte 1 — Estado del proyecto

¡Hola! Les comparto cómo vamos con la migración de Spotfire a Power BI. 🙂

**Ya quedó lista la primera parte** (pasos 2 y 3 del diagrama: leer el .dxp y generar el .tmdl).

**¿Qué hace la herramienta?**
Le das un archivo .dxp y te entrega tres cosas:

- **Un documento de referencia**: fuentes de datos, tablas, columnas con sus tipos, relaciones,
  fórmulas, y una lista de las páginas y gráficos para armar el reporte.
- **El modelo de Power BI** (.tmdl): tablas, columnas, medidas y la consulta que lee el archivo de
  datos. La ruta del archivo queda como parámetro, así que solo se cambia en un lugar.
- **La lista de fórmulas** traducidas de Spotfire a Power BI.

**Lo probamos con 5 análisis** (Viajes2024 y 4 demos de Spotfire). Los cinco generan su modelo y
pasan la revisión automática sin errores. Viajes2024 quedó completo, sin pendientes.

**Las fórmulas sencillas se traducen solas.** Por ejemplo, `Sum([Tarifa])` pasa a
`SUM('Viajes2024'[Tarifa])`. Las difíciles no se adivinan: se marcan y las completamos con ayuda
de la IA, que ya quedó configurada en el proyecto.

**Lo que sigue**

- Armar los gráficos del reporte (eso todavía es a mano, con la lista que genera la herramienta).
- Abrir el modelo en Power BI Desktop para confirmar que carga bien. Esta prueba aún no la hacemos.

**Lo que necesitamos de ustedes**

1. Los archivos de datos (CSV/Excel). El .dxp solo guarda la ruta de la computadora del autor, no
   los datos.
2. Algunos .dxp reales de su Spotfire, para probar con casos de verdad.
3. Una computadora con Windows y Power BI Desktop, aunque sea prestada un rato. Nosotros
   trabajamos en Mac y esa prueba necesita Windows.

**Dos detalles**

- Si un análisis usa archivos SBDF (formato propio de Spotfire), hay que exportarlos a CSV, porque
  Power BI no los lee.
- En Viajes2024 hay una columna con un carácter raro ("est‡" en lugar de "está"). Con el CSV
  original lo confirmamos.

Cualquier duda me dicen. ¡Gracias!

---

## Parte 2 — Herramientas y flujo de trabajo

**¿Con qué lo hacemos?**

- **Spotfire**: solo para exportar el archivo .dxp. Después ya no hace falta.
- **dxp2pbi**: una herramienta que hicimos nosotros (en Python). Es la que lee el .dxp y escribe el
  documento y el modelo. Corre en Mac, sin instalar Spotfire ni Power BI.
- **Claude Code**: el asistente de IA, que trabaja dentro del mismo proyecto. Le enseñamos tres
  "rutinas": una arma el documento, otra traduce las fórmulas difíciles y otra hace todo de corrido.
- **Power BI Desktop** (en Windows): solo al final, para abrir el modelo y armar los gráficos.
- **Git**: ahí vive el código y queda el historial de cambios.

**¿Cómo es el flujo?**

1. Exportamos el .dxp desde Spotfire, junto con su archivo de datos. 👈 esto es manual
2. Corremos **un comando**. La herramienta lee el .dxp y genera el documento de referencia y el
   modelo de Power BI.
3. Las fórmulas que la herramienta no pudo traducir quedan marcadas, y la **IA las completa**. Nada
   se adivina: lo que no se puede traducir, se anota como pendiente.
4. Cada vez que se toca algo, una **revisión automática** vuelve a generar el modelo y avisa si algo
   quedó mal. Así no se nos pasa un error.
5. Abrimos el modelo en **Power BI Desktop** y le indicamos dónde está el archivo de datos (es un
   solo dato que cambiar).
6. Armamos los gráficos siguiendo la lista del documento, comparando con la imagen del tablero
   original.

En resumen: los pasos 2, 3 y 4 son automáticos; el 1, el 5 y el 6 son a mano, por ahora.
