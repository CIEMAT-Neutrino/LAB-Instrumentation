import pyvisa
rm = pyvisa.ResourceManager("@py") #Gestor de recursos que busca y abre instrumentos
print(rm.list_resources())
gen = rm.open_resource(rm.list_resources()[0])
gen.timeout = 5000
print(gen.query("*IDN?"))