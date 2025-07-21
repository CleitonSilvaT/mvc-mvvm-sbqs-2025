import pandas as pd
import numpy as np
from pathlib import Path
from scipy.stats import shapiro

# 1. CONFIGURAÇÃO INICIAL
caminho_csv = Path('Instrumentos/Codigos/repositoriosTestadosCoverletV2.csv')

# 2. LER CSV COM TRATAMENTO DE CAMPOS VAZIOS
try:
    df = pd.read_csv(caminho_csv, keep_default_na=True, na_values=['', ' ', 'NA', 'N/A'])
except Exception as e:
    print(f"Erro ao ler o arquivo CSV: {e}")
    exit()

# 3. NORMALIZAR COLUNA 'Arquitetura'
df['Arquitetura'] = df['Arquitetura'].astype(str).str.strip().str.upper()

# 4. CONVERTER COLUNAS DE PORCENTAGEM
def converter_porcentagem(valor):
    if pd.isna(valor) or str(valor).strip() in ['', 'NAN', 'N/A']:
        return np.nan
    if isinstance(valor, str):
        return float(valor.replace('%', '').strip()) / 100
    return float(valor)

df['Cobertura Linha (%)'] = df['Cobertura Linha (%)'].apply(converter_porcentagem)
df['Mutation Score'] = df['Mutation Score'].apply(converter_porcentagem)

# 5. CALCULAR MÉTRICA DE ERRO DE COMPILAÇÃO
df['Mutantes Erro Compilação (%)'] = (df['Mutants Compile Error'] / df['Total Mutants']) * 100

# 6. TESTE DE NORMALIDADE
metricas = ['Mutation Score', 'Cobertura Linha (%)', 'Mutantes Erro Compilação (%)']

print("\n=== TESTE DE NORMALIDADE: SHAPIRO-WILK ===")

for metrica in metricas:
    print(f"\n Métrica: {metrica}")
    
    for arquitetura in ['MVC', 'MVVM']:
        dados = df[df['Arquitetura'] == arquitetura][metrica].dropna()
        
        if len(dados) < 3:
            print(f"{arquitetura} - Poucos dados para o teste (n={len(dados)})")
            continue
        
        print(f"   Valores usados ({arquitetura}): {dados.values}")
        stat, p = shapiro(dados)
        normal = 'Sim' if p > 0.05 else 'Não'
        print(f"🔹 {arquitetura} → p-value = {p:.4f} → Distribuição Normal? {normal}")
