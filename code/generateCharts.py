import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
from scipy.stats import linregress

# 1. CONFIGURAÇÃO INICIAL
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 12
palette = {'MVC': '#1f77b4', 'MVVM': '#ff7f0e'}

# 2. CARREGAR DADOS CORRETAMENTE
caminho_csv = Path('Instrumentos/Codigos/repositoriosTestadosCoverletV2.csv')

try:
    df = pd.read_csv(caminho_csv, keep_default_na=True, na_values=['', ' ', 'NA', 'N/A'])
except Exception as e:
    print(f"Erro ao ler o arquivo CSV: {e}")
    exit()

# 3. VERIFICAÇÃO INICIAL
print("\n=== VERIFICAÇÃO INICIAL ===")
print("Colunas disponíveis:", df.columns.tolist())
print("\nValores únicos em 'Arquitetura':", df['Arquitetura'].unique())

df['Arquitetura'] = df['Arquitetura'].astype(str).str.strip().str.upper()

def converter_porcentagem(valor):
    if pd.isna(valor) or str(valor).strip() in ['', 'NAN', 'N/A']:
        return np.nan
    if isinstance(valor, str):
        return float(valor.replace('%', '').strip()) / 100
    return float(valor)

df['Cobertura Linha (%)'] = df['Cobertura Linha (%)'].apply(converter_porcentagem)
df['Mutation Score'] = df['Mutation Score'].apply(converter_porcentagem)
df['Mutantes Erro Compilação (%)'] = (df['Mutants Compile Error'] / df['Total Mutants']) * 100

# 7. VERIFICAÇÃO FINAL
print("\n=== DADOS PROCESSADOS ===")
print(f"Total de projetos válidos: {len(df)}")
print(f"Projetos MVC: {len(df[df['Arquitetura'] == 'MVC'])}")
print(f"Projetos MVVM: {len(df[df['Arquitetura'] == 'MVVM'])}")

if len(df) == 0:
    print("\nERRO: Nenhum dado válido encontrado!")
    exit()

# 8. INTERVALO INTERQUARTIL (IQR)
def exibir_iqr(coluna, nome_coluna_exibicao):
    print(f"\n=== IQR de '{nome_coluna_exibicao}' por Arquitetura ===")
    for arquitetura, grupo in df.groupby('Arquitetura'):
        q1 = grupo[coluna].quantile(0.25)
        q3 = grupo[coluna].quantile(0.75)
        iqr = q3 - q1
        print(f"{arquitetura}: Q1 = {q1:.3f}, Q3 = {q3:.3f}, IQR = {iqr:.3f}")

exibir_iqr('Mutation Score', 'Mutation Score')
exibir_iqr('Cobertura Linha (%)', 'Cobertura de Linhas')
exibir_iqr('Mutantes Erro Compilação (%)', 'Mutantes com Erro de Compilação')

# 9. GERAR GRÁFICOS
try:
    print("\n=== MEDIANAS POR ARQUITETURA ===")
    for coluna in ['Mutation Score', 'Cobertura Linha (%)', 'Mutantes Erro Compilação (%)']:
        print(f"\nMedianas de '{coluna}':")
        medianas = df.groupby('Arquitetura')[coluna].median()
        for arquitetura, mediana in medianas.items():
            print(f"  {arquitetura}: {mediana:.3f}")
            
    # Gráfico 1: Mutation Score
    plt.figure(figsize=(14, 6))
    sns.boxplot(data=df, x='Arquitetura', y='Mutation Score', palette=palette, hue='Arquitetura', legend=False)
    plt.title('Mutation Score por Arquitetura')
    plt.ylabel('Score (0-1)')
    plt.show()

    # Gráfico 2: Cobertura de Linhas
    plt.figure(figsize=(14, 6))
    sns.boxplot(data=df, x='Arquitetura', y='Cobertura Linha (%)', palette=palette, hue='Arquitetura', legend=False)
    plt.title('Cobertura de Linhas por Arquitetura')
    plt.ylabel('Cobertura (0-1)')
    plt.xlabel('Arquitetura')
    plt.show()

    print("\n=== COEFICIENTES DE REGRESSÃO LINEAR ===")

    for arquitetura in ['MVC', 'MVVM']:
        grupo = df[df['Arquitetura'] == arquitetura].dropna(subset=['Cobertura Linha (%)', 'Mutation Score'])
        if len(grupo) >= 3:
            x = grupo['Cobertura Linha (%)'].values
            y = grupo['Mutation Score'].values
            slope, intercept, r_value, p_value, std_err = linregress(x, y)

            print(f"\nArquitetura: {arquitetura}")
            print(f"  Inclinação (slope): {slope:.4f}")
            print(f"  Intercepto: {intercept:.4f}")
            print(f"  Coeficiente de Correlação (r): {r_value:.4f}")
            print(f"  Valor-p: {p_value:.4f}")
            print(f"  Erro padrão: {std_err:.4f}")
        else:
            print(f"\nArquitetura: {arquitetura}")
            print("  Não há dados suficientes para calcular a regressão linear.")

    # Gráfico 3: Relação Cobertura vs Mutation Score + Regressão Linear
    plt.figure(figsize=(14, 6))
    arquiteturas = df['Arquitetura'].unique()
    df_mvc = df[df['Arquitetura'] == 'MVC'].dropna(subset=['Cobertura Linha (%)', 'Mutation Score'])
    for arquitetura in arquiteturas:
        grupo = df[df['Arquitetura'] == arquitetura].dropna(subset=['Cobertura Linha (%)', 'Mutation Score'])
        x = grupo['Cobertura Linha (%)'].values
        y = grupo['Mutation Score'].values
        
        # Scatter individual
        sns.scatterplot(x=x, y=y, color=palette[arquitetura], label=f'{arquitetura} dados', s=100)

        # Regressão linear
        slope, intercept, r_value, p_value, std_err = linregress(x, y)
        linha_x = np.linspace(x.min(), x.max(), 100)
        linha_y = slope * linha_x + intercept
        plt.plot(linha_x, linha_y, color=palette[arquitetura], linestyle='--',
                 label=f'{arquitetura} regressão (r={r_value:.2f})')

    plt.title('Relação entre Cobertura de Linhas e Mutation Score (com Regressão Linear)')
    plt.xlabel('Cobertura de Linhas (0-1)')
    plt.ylabel('Mutation Score (0-1)')
    plt.legend()
    plt.grid(True)
    plt.show()

    # Gráfico 4: Erro de Compilação
    plt.figure(figsize=(14, 6))
    sns.boxplot(data=df, x='Arquitetura', y='Mutantes Erro Compilação (%)', palette=palette, hue='Arquitetura', legend=False)
    plt.title('Distribuição da Proporção de Mutantes com Erro de Compilação')
    plt.ylabel('Mutantes com Erro de Compilação (%)')
    plt.xlabel('Arquitetura')
    plt.ylim(0, 30)  
    plt.show()

    # Gráfico 5: Idade do Repositório vs Mutation Score
    print("\n=== GRÁFICO: Idade do Repositório vs Mutation Score ===")
    caminho_csvAge = Path('Instrumentos/Codigos/repositoriosIdade.csv')

    df_idade = pd.read_csv(caminho_csvAge, keep_default_na=True, na_values=['', ' ', 'NA', 'N/A'])
    df_idade['Arquitetura'] = df_idade['Arquitetura'].astype(str).str.strip().str.upper()
    df_idade['Mutation Score'] = df_idade['Mutation Score'].apply(converter_porcentagem)

    df_valido = df_idade.dropna(subset=['Idade (anos)', 'Mutation Score'])

    plt.figure(figsize=(12, 6))
    
    # Plotar os pontos coloridos por arquitetura
    sns.scatterplot(data=df_valido, x='Idade (anos)', y='Mutation Score', hue='Arquitetura', palette=palette, s=100)

    # Para cada arquitetura, calcula e plota a linha de regressão separada
    for arquitetura in ['MVC', 'MVVM']:
        grupo = df_valido[df_valido['Arquitetura'] == arquitetura]
        if len(grupo) >= 3:
            x = grupo['Idade (anos)'].values
            y = grupo['Mutation Score'].values
            slope, intercept, r_value, p_value, std_err = linregress(x, y)
            linha_x = np.linspace(x.min(), x.max(), 100)
            linha_y = slope * linha_x + intercept
            plt.plot(linha_x, linha_y, linestyle='--', label=f'{arquitetura} regressão (r={r_value:.2f})', color=palette[arquitetura])
            
            print(f"{arquitetura}: r = {r_value:.4f}, p = {p_value:.4f}")
        else:
            print(f"Arquitetura {arquitetura}: dados insuficientes para regressão.")

    plt.title('Idade do Repositório vs Mutation Score com Regressão por Arquitetura')
    plt.xlabel('Idade do Repositório (anos)')
    plt.ylabel('Mutation Score (0-1)')
    plt.legend()
    plt.grid(True)
    plt.show()

except Exception as e:
    print(f"\nErro ao gerar gráficos: {e}")