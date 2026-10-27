"""Punto de entrada del ejecutable: abre la aplicación, o el simulador con --simulador.

    AUREA Sentinel.exe                      # la aplicación
    AUREA Sentinel.exe --simulador          # genera lecturas de los 36 sensores (acepta --intervalo, --ciclos…)
"""
import sys

if "--simulador" in sys.argv:
    sys.argv.remove("--simulador")
    from simulador.__main__ import main
    main()
else:
    from cliente.controlador.aplicacion import main
    sys.exit(main())
