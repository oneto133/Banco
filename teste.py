from random import randint

numero_aleatorio = randint(1, 60)

lista = []
while numero_aleatorio not in lista:
    lista.append(numero_aleatorio)
    numero_aleatorio = randint(1, 60)
    if len(lista) == 6:
        break
                           
print(sorted(lista))