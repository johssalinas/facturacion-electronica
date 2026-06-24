import re


def _solo_digitos(valor):
	return re.sub(r"\D", "", str(valor or ""))


def calcular_dv(nit):
	nit = _solo_digitos(nit)
	if not nit:
		return ""
	pesos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 47, 53, 59, 67, 71, 73]
	total = 0
	for i in range(len(nit)):
		digito = int(nit[len(nit) - 1 - i])
		total += digito * pesos[i]
	resto = total % 11
	if resto <= 1:
		return str(resto)
	return str(11 - resto)


def validar_dv_nit(nit, dv):
	if not nit or dv is None:
		return False
	return calcular_dv(nit) == str(dv).strip()
