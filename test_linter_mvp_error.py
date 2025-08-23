# Test-Datei für Linter-Konfiguration
# Diese Datei soll absichtlich einen Stilfehler enthalten der erkannt wird


def bad_function():
    pass  # F841: unused variable
    
def test_function( ):  # E201: whitespace after '('
    print("Test")
    
# Fehlende Imports (sollte von I-Regeln erkannt werden)

print("MVP-Modul mit absichtlichen Stilfehlern")
