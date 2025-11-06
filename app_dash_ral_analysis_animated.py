import zipfile
from pathlib import Path

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
import io, base64

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])

app.title = "Análise de RALs - Tema Escuro Animado"

app.layout = dbc.Container([
    html.H2("📊 Dashboard de RALs", className="text-center my-4"),
    dcc.Upload(
        id="upload-data",
        children=html.Div(["Arraste e solte ou ", html.A("selecione um arquivo Excel (.xlsx)")]),
        style={
            "width": "100%", "height": "80px", "lineHeight": "80px",
            "borderWidth": "2px", "borderStyle": "dashed",
            "borderRadius": "10px", "textAlign": "center", "margin": "10px"
        },
        multiple=False
    ),
    html.Div(id="output-data-upload")
], fluid=True)

def parse_excel(contents, filename):
    content_type, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)
    try:
        df = pd.read_excel(io.BytesIO(decoded))

        ral_col = "RAL/INC CADASTRADOS"
        alarm_col = "HORÁRIO ALARME"
        norm_col = "HORÁRIO NORMALIZAÇÃO"

        # Filtrar apenas RALs preenchidas
        df[ral_col] = df[ral_col].astype(str).str.strip()
        df = df[df[ral_col].notna() & (df[ral_col] != "") & (df[ral_col].str.lower() != "nan")]

        # Conversão de datas com formato fixo
        df[alarm_col] = pd.to_datetime(df[alarm_col], format="%d/%m/%Y %H:%M:%S", errors="coerce")
        df[norm_col] = pd.to_datetime(df[norm_col], format="%d/%m/%Y %H:%M:%S", errors="coerce")

        # Reatribuição segura (sem inplace)
        df[alarm_col] = df[alarm_col].fillna(pd.to_datetime(df[alarm_col], format="%d/%m/%Y %H:%M", errors="coerce"))
        df[norm_col] = df[norm_col].fillna(pd.to_datetime(df[norm_col], format="%d/%m/%Y %H:%M", errors="coerce"))

        df["Tempo de Recuperação (min)"] = (df[norm_col] - df[alarm_col]).dt.total_seconds() / 60
        df = df[df["Tempo de Recuperação (min)"] >= 0]

        return df

    except Exception as e:
        print(f"Erro ao processar arquivo: {e}")
        return pd.DataFrame()

@app.callback(Output("output-data-upload", "children"),
              Input("upload-data", "contents"),
              State("upload-data", "filename"))
def update_output(contents, filename):
    if contents is None:
        return html.Div("Nenhum arquivo carregado ainda.")

    df = parse_excel(contents, filename)
    if df.empty:
        return html.Div("❌ Nenhuma linha válida encontrada na planilha.")

    # KPIs
    total_rals = len(df)
    media_tempo = df["Tempo de Recuperação (min)"].mean()
    max_tempo = df["Tempo de Recuperação (min)"].max()
    min_tempo = df["Tempo de Recuperação (min)"].min()

    faixas = {
        "≤ 5 min": len(df[df["Tempo de Recuperação (min)"] <= 5]),
        "≤ 10 min": len(df[(df["Tempo de Recuperação (min)"] > 5) & (df["Tempo de Recuperação (min)"] <= 10)]),
        "≤ 15 min": len(df[(df["Tempo de Recuperação (min)"] > 10) & (df["Tempo de Recuperação (min)"] <= 15)])
    }

    graf_bar = px.bar(
        df.groupby(df["HORÁRIO ALARME"].dt.date).size().reset_index(name="Rals"),
        x="HORÁRIO ALARME", y="Rals",
        title="Rals abertas por dia",
        template="plotly_dark"
    )

    graf_pie = px.pie(
        names=list(faixas.keys()),
        values=list(faixas.values()),
        title="Distribuição por tempo de recuperação",
        template="plotly_dark"
    )

    return html.Div([
        html.Div([
            dbc.Row([
                dbc.Col(dbc.Card([html.H5("Total RALs"), html.H2(f"{total_rals:,}")]), md=3),
                dbc.Col(dbc.Card([html.H5("Média (min)"), html.H2(f"{media_tempo:.1f}")]), md=3),
                dbc.Col(dbc.Card([html.H5("Máximo (min)"), html.H2(f"{max_tempo:.1f}")]), md=3),
                dbc.Col(dbc.Card([html.H5("Mínimo (min)"), html.H2(f"{min_tempo:.1f}")]), md=3),
            ], className="text-center my-4"),
        ]),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=graf_bar, animate=True), md=6),
            dbc.Col(dcc.Graph(figure=graf_pie, animate=True), md=6),
        ])
    ])

if __name__ == "__main__":
    app.run(debug=True)
