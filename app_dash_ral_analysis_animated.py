import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
import io, base64, re
from dash.exceptions import PreventUpdate
from dash import callback_context
from dash_extensions.enrich import Trigger
from dash import no_update
from dash import dcc

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG]) 
app.config.suppress_callback_exceptions = True
app.title = "Relatório de Alarmes"
server = app.server

# ========== LAYOUT ==========
app.layout = dbc.Container([
    html.H2("📊 Relatório de Alarmes", className="text-center my-4"),

    # Upload de planilha
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

    # Abas
    dbc.Tabs(
        [
            dbc.Tab(label="📈 Relatório de Alarmes", tab_id="aba_geral",
                    label_style={"color": "white"}, tab_style={"backgroundColor": "#222"}),
            dbc.Tab(label="⚙️ Relatório de RALs", tab_id="aba_rals",
                    label_style={"color": "white"}, tab_style={"backgroundColor": "#222"}),
        ],
        id="tabs",
        active_tab="aba_geral",
        style={"backgroundColor": "#111", "color": "white", "borderRadius": "10px"}
    ),

    # Dropdown de centros (dinâmico)
    html.Div(id="filtro-centro-container", style={"marginTop": "20px"}),

    # Conteúdo dinâmico (fade in)
    html.Div(id="output-data-upload", className="animate__animated animate__fadeIn")

], fluid=True)


# ========== FUNÇÃO DE LEITURA ==========
def parse_excel(contents, filename):
    content_type, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)
    try:
        df = pd.read_excel(io.BytesIO(decoded))

        ral_col = "RAL/INC CADASTRADOS"
        alarm_col = "HORÁRIO ALARME"
        norm_col = "HORÁRIO NORMALIZAÇÃO"

        # 👉 Mantém todas as linhas (inclusive RALs vazias)
        df[ral_col] = df[ral_col].fillna("").astype(str).str.strip()

        # Conversão de datas
        df[alarm_col] = pd.to_datetime(df[alarm_col], format="%d/%m/%Y %H:%M:%S", errors="coerce")
        df[norm_col] = pd.to_datetime(df[norm_col], format="%d/%m/%Y %H:%M:%S", errors="coerce")

        # Reatribuição segura (sem inplace)
        df[alarm_col] = df[alarm_col].fillna(pd.to_datetime(df[alarm_col], format="%d/%m/%Y %H:%M", errors="coerce"))
        df[norm_col] = df[norm_col].fillna(pd.to_datetime(df[norm_col], format="%d/%m/%Y %H:%M", errors="coerce"))

        # Cálculo do tempo de recuperação
        df["Tempo de Recuperação (min)"] = (df[norm_col] - df[alarm_col]).dt.total_seconds() / 60
        df = df[df["Tempo de Recuperação (min)"] >= 0]

        return df

    except Exception as e:
        print(f"Erro ao processar arquivo: {e}")
        return pd.DataFrame()


# ========== CALLBACK 1 — Atualiza dropdown de centros ==========
@app.callback(
    Output("filtro-centro-container", "children"),
    Input("upload-data", "contents"),
    State("upload-data", "filename"),
)
def atualizar_dropdown_centros(contents, filename):
    if contents is None:
        return no_update

    df = parse_excel(contents, filename)
    if "CENTRO" not in df.columns:
        return html.Div("⚠️ Coluna 'CENTRO' não encontrada na planilha.", className="text-warning")

    centros_unicos = sorted(df["CENTRO"].dropna().unique())
    return dbc.Row([
        dbc.Col(html.Label("🔍 Filtrar por Centro:"), md=3),
        dbc.Col(
            dcc.Dropdown(
                id="dropdown-centro",
                options=[{"label": c, "value": c} for c in centros_unicos],
                placeholder="Selecione um centro (ou deixe em branco para todos)",
                multi=False,
                style={"color": "black"}
            ), md=6
        )
    ], className="my-3")


# ========== CALLBACK 2 — Atualiza conteúdo das abas ==========
@app.callback(
    Output("output-data-upload", "children"),
    Input("upload-data", "contents"),
    State("upload-data", "filename"),
    Input("tabs", "active_tab"),
    Input("dropdown-centro", "value")
)
def update_output(contents, filename, aba, centro_filtro):
    if contents is None:
        raise PreventUpdate
    graf_pie_ral = graf_centro_div = graf_centros_div = graf_centro = None

    df = parse_excel(contents, filename)
    if df.empty:
        return html.Div("❌ Nenhuma linha válida encontrada.", style={"textAlign": "center"})

    ral_col = "RAL/INC CADASTRADOS"
    tempo_col = "Tempo de Recuperação (min)"

    # Filtro de centro
    if centro_filtro and "CENTRO" in df.columns:
        df = df[df["CENTRO"] == centro_filtro]

    # ===== ABA 1: RELATÓRIO DE ALARMES =====
    if aba == "aba_geral":
        total_linhas = len(df)  # todas as linhas válidas (não só numéricas)
        media_tempo = df[tempo_col].mean()
        max_tempo = df[tempo_col].max()
        min_tempo = df[tempo_col].min()

        faixas = {
            "≤ 5 min": len(df[df[tempo_col] <= 5]),
            "≤ 10 min": len(df[(df[tempo_col] > 5) & (df[tempo_col] <= 10)]),
            "≤ 15 min": len(df[(df[tempo_col] > 10) & (df[tempo_col] <= 15)]),
            "> 15 min": len(df[df[tempo_col] > 15])
        }

        graf_bar = px.bar(
            df.groupby(df["HORÁRIO ALARME"].dt.date).size().reset_index(name="Alarmes"),
            x="HORÁRIO ALARME", y="Alarmes",
            title="Alarmes por Dia",
            template="plotly_dark"
        )

        graf_pie = px.pie(
            names=list(faixas.keys()),
            values=list(faixas.values()),
            title="Distribuição por Tempo de Recuperação",
            template="plotly_dark"
        )

        if "CENTRO" in df.columns:
            centro_count = df["CENTRO"].value_counts().reset_index()
            centro_count.columns = ["CENTRO", "Total de Alarmes"]

            graf_centro = px.bar(
                centro_count,
                x="Total de Alarmes",
                y="CENTRO",
                text="Total de Alarmes",
                title="Alarmes por Centro",
                template="plotly_dark",
                orientation="h"  # 🔹 gráfico horizontal
            )

            graf_centro.update_layout(
                xaxis_title="Total de Alarmes",
                yaxis_title="Centros",
                height=600,
                margin=dict(l=100, r=40, t=80, b=40)
            )

            # 🔹 Container com rolagem caso haja muitos centros
            graf_centro_div = html.Div(
                dcc.Graph(figure=graf_centro, animate=True),
                style={"overflowY": "auto", "maxHeight": "600px"}  # 🔹 Scroll vertical
            )

        else:
            graf_centro_div = html.Div("Coluna 'CENTRO' não encontrada.")
        return html.Div([
            dbc.Row([
                dbc.Col(dbc.Card([html.H5("Linhas com dados"), html.H2(f"{total_linhas:,}")]), md=3),
                dbc.Col(dbc.Card([html.H5("Média (min)"), html.H2(f"{media_tempo:.1f}")]), md=3),
                dbc.Col(dbc.Card([html.H5("Máximo (min)"), html.H2(f"{max_tempo:.1f}")]), md=3),
                dbc.Col(dbc.Card([html.H5("Mínimo (min)"), html.H2(f"{min_tempo:.1f}")]), md=3),
            ], className="text-center my-4"),

            dbc.Row([
                dbc.Col(dcc.Graph(figure=graf_bar, animate=True), md=6),
                dbc.Col(dcc.Graph(figure=graf_pie, animate=True), md=6),
            ]),

            html.Hr(),

            graf_centro_div
        ], className="animate__animated animate__fadeIn")

    # ===== ABA 2: RELATÓRIO DE RALS =====
    elif aba == "aba_rals":
        # Linhas com números em RAL
        df_rals = df[df[ral_col].str.contains(r"\d", na=False)]

        total_rals = len(df_rals)  # apenas linhas com números
        media_tempo = df_rals[tempo_col].mean()
        max_tempo = df_rals[tempo_col].max()
        min_tempo = df_rals[tempo_col].min()

        faixas_ral = {
            "≤ 5 min": len(df_rals[df_rals[tempo_col] <= 5]),
            "≤ 10 min": len(df_rals[(df_rals[tempo_col] > 5) & (df_rals[tempo_col] <= 10)]),
            "≤ 15 min": len(df_rals[(df_rals[tempo_col] > 10) & (df_rals[tempo_col] <= 15)]),
            "> 15 min": len(df_rals[df_rals[tempo_col] > 15])
        }

        if "CENTRO" in df_rals.columns:
            centro_count = df_rals["CENTRO"].value_counts().reset_index()
            centro_count.columns = ["CENTRO", "Total de RALs"]

            graf_centros = px.bar(
                centro_count,
                x="Total de RALs",
                y="CENTRO",
                text="Total de RALs",
                title="RALs por Centro",
                template="plotly_dark",
                orientation="h"  # 🔹 horizontal
            )

            graf_centros.update_layout(
                xaxis_title="Total de RALs",
                yaxis_title="Centros",
                height=600,
                margin=dict(l=100, r=40, t=80, b=40)
            )

            graf_centros_div = html.Div(
                dcc.Graph(figure=graf_centros, animate=True),
                style={"overflowY": "auto", "maxHeight": "600px"}  # 🔹 Scroll vertical
            )
        else:
            graf_centros_div = html.Div("Coluna 'CENTRO' não encontrada.")

        graf_pie_ral = px.pie(
            names=list(faixas_ral.keys()),
            values=list(faixas_ral.values()),
            title="Distribuição das RALs por Faixa de Tempo",
            template="plotly_dark"
        )

        return html.Div([
            dbc.Row([
                dbc.Col(dbc.Card([html.H5("Total de RALs"), html.H2(f"{total_rals:,}")]), md=3),
                dbc.Col(dbc.Card([html.H5("Média (min)"), html.H2(f"{media_tempo:.1f}")]), md=3),
                dbc.Col(dbc.Card([html.H5("Máximo (min)"), html.H2(f"{max_tempo:.1f}")]), md=3),
                dbc.Col(dbc.Card([html.H5("Mínimo (min)"), html.H2(f"{min_tempo:.1f}")]), md=3),
            ], className="text-center my-4"),

            dbc.Row([
                dbc.Col(dcc.Graph(figure=graf_pie_ral, animate=True), md=6),
                dbc.Col(graf_centros_div, md=6)
            ]),
        ], className="animate__animated animate__fadeIn")


if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8080)