"""
GraphRAG 可视化 — Dash Cytoscape 实现

功能：
1. 节点大小随滑块变化，文字自适应缩放
2. 滚轮缩放
3. 多选节点 + 邻居高亮
4. 点击跳转 + 历史栈回退
5. Hover 显示关系 + 关系类型筛选面板
6. 可搜索干员列表（解决1382节点全量渲染卡顿问题）
"""
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_cytoscape as cyto
import networkx as nx
from collections import defaultdict
from pathlib import Path

# ─── Graph Data Loader ──────────────────────────────────────────────────────────

def load_graph():
    """Load entity-relations.json into NetworkX graph."""
    path = str(Path(__file__).parent.parent.parent / 'chunks/graphrag/entity_relations.json')
    if not Path(path).exists():
        return None

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    G = nx.Graph()
    for e in data.get('entities', []):
        G.add_node(e['entity'], type=e.get('type', '干员'))

    for r in data.get('relations', []):
        G.add_edge(
            r['source'], r['target'],
            relation=r.get('relation', ''),
            description=r.get('description', '')
        )
    return G

def get_relation_types(G):
    """Return sorted list of all unique relation types."""
    rels = set()
    for u, v, d in G.edges(data=True):
        rel = d.get('relation', '')
        if rel:
            rels.add(rel)
    return sorted(rels)

# ─── Cytoscape Stylesheet ──────────────────────────────────────────────────────

def make_stylesheet(node_size: int, text_size: int, selected_nodes: list, neighbor_nodes: list,
                   visible_rels: set, G):
    """Build Cytoscape stylesheet with dynamic node size and relation filtering."""
    label_size = text_size

    node_defaults = {
        'shape': 'ellipse',
        'width': node_size,
        'height': node_size,
        'backgroundColor': '#26C6DA',
        'borderWidth': 1.5,
        'borderColor': '#90A4AE',
        'label': 'data(label)',
        'color': '#1a1a1a',
        'fontSize': label_size,
        'textValign': 'center',
        'textHalign': 'center',
    }

    selected_style = {
        **node_defaults,
        'backgroundColor': '#FF7043',
        'borderColor': '#bf360c',
        'borderWidth': 2.5,
    }

    neighbor_style = {
        **node_defaults,
        'backgroundColor': '#80DEEA',
        'borderColor': '#0097A7',
    }

    styles = [{'selector': 'node', 'style': node_defaults}]

    for n in selected_nodes:
        styles.append({'selector': f'node[id = "{n}"]', 'style': selected_style})

    if selected_nodes and neighbor_nodes:
        for n in neighbor_nodes:
            if n not in selected_nodes:
                styles.append({'selector': f'node[id = "{n}"]', 'style': neighbor_style})

    edge_default = {
        'opacity': 0.15,
        'width': 1,
        'lineColor': '#78909C',
    }
    styles.append({'selector': 'edge', 'style': edge_default})

    selected_set = set(selected_nodes)
    for u, v, d in G.edges(data=True):
        rel = d.get('relation', '')
        if rel in visible_rels:
            eid = f"{u}\t{v}"
            is_related = (u in selected_set or v in selected_set)
            styles.append({
                'selector': f'edge[id = "{eid}"]',
                'style': {
                    'opacity': 0.7,
                    'width': 1.5,
                    'lineColor': '#FF7043' if is_related else '#26C6DA',
                    'targetArrowColor': '#FF7043' if is_related else '#26C6DA',
                    'arrowScale': 0.7,
                }
            })

    return styles

def build_elements(G, visible_nodes: set, visible_rels: set):
    """Build Cytoscape elements — only includes visible_nodes (selected + neighbors)."""
    elements = []

    for node in visible_nodes:
        degree = G.degree(node)
        elements.append({
            'data': {'id': node, 'label': node, 'degree': degree}
        })

    for u, v, d in G.edges(data=True):
        rel = d.get('relation', '')
        if rel in visible_rels and u in visible_nodes and v in visible_nodes:
            elements.append({
                'data': {
                    'id': f"{u}\t{v}",
                    'source': u,
                    'target': v,
                    'relation': rel,
                    'description': d.get('description', ''),
                    'label': rel,
                }
            })

    return elements

def get_initial_elements(G, all_rels: list):
    """Initial render: top-degree nodes + their edges, capped at 80 nodes."""
    nodes_by_degree = sorted(G.nodes(), key=lambda n: G.degree(n), reverse=True)
    initial_nodes = set(nodes_by_degree[:20])

    for n in list(initial_nodes):
        initial_nodes.update(G.neighbors(n))

    if len(initial_nodes) > 80:
        nodes_by_degree_80 = sorted(initial_nodes, key=lambda n: G.degree(n), reverse=True)
        initial_nodes = set(nodes_by_degree_80[:80])

    visible = set(all_rels)
    return build_elements(G, initial_nodes, visible), initial_nodes

# ─── Dash App ────────────────────────────────────────────────────────────────

def create_dash_app(flask_host='127.0.0.1', flask_port=8050):
    G = load_graph()
    if G is None:
        raise RuntimeError("entity_relations.json not found. Run GraphRAG extractor first.")

    all_nodes = sorted(G.nodes())
    all_rels = get_relation_types(G)
    all_node_options = [{'label': n, 'value': n} for n in all_nodes]

    initial_elements, initial_visible = get_initial_elements(G, all_rels)

    app = dash.Dash(__name__)
    app.title = "GraphRAG 可视化"

    app.layout = html.Div([
        html.H2("GraphRAG 关系图谱", style={'textAlign': 'center'}),

        html.Div(id='current-selection-display', children=["当前选中：无"],
                 style={'textAlign': 'center', 'fontSize': '14px', 'color': '#666', 'marginBottom': '8px'}),

        # Edge info display
        html.Div(id='edge-info', children=["点击关系线查看关系类型"],
                 style={'textAlign': 'center', 'fontSize': '13px', 'color': '#888', 'marginBottom': '8px', 'minHeight': '20px'}),

        html.Div([
            # Left: Controls panel
            html.Div([
                html.H4("控制面板", style={'marginTop': 0}),

                # Searchable operator list
                html.Label("快速定位干员"),
                dcc.Dropdown(
                    id='operator-search',
                    options=all_node_options,
                    placeholder='输入干员名...',
                    searchable=True,
                    clearable=True,
                    style={'fontSize': '12px'},
                ),

                html.Hr(),

                # Selected operators chips
                html.Label("已选中干员"),
                html.Div(id='selected-chips', children=[
                    html.Span("无", style={'color': '#999', 'fontSize': '11px'})
                ], style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '4px', 'minHeight': '24px'}),

                html.Hr(),

                # Node size
                html.Label("节点大小"),
                dcc.Slider(id='node-size-slider', min=8, max=120, step=2,
                           value=40, tooltip={'placement': 'bottom', 'always_visible': True}),

                # Text size
                html.Label("文字大小"),
                dcc.Slider(id='text-size-slider', min=6, max=32, step=1,
                           value=14, tooltip={'placement': 'bottom', 'always_visible': True}),

                html.Hr(),

                # Relation type filter
                html.Label("关系类型筛选"),
                html.Div([
                    dcc.Checklist(
                        id='relation-filter',
                        options=[{'label': r, 'value': r} for r in all_rels],
                        value=all_rels,
                        inline=False,
                        style={'fontSize': '12px'},
                        inputStyle={'marginRight': '4px', 'marginBottom': '2px'},
                    )
                ], style={'fontSize': '12px', 'maxHeight': '200px', 'overflowY': 'scroll'}),

                html.Hr(),

                # Selected detail
                html.H4("选中详情", style={'fontSize': '13px'}),
                html.Div(id='selection-detail', style={'fontSize': '11px', 'color': '#444'}),

                html.Hr(),

                # Back / Reset
                html.Div([
                    html.Button('← 回退', id='back-btn', n_clicks=0,
                               style={'marginRight': '8px', 'padding': '4px 12px'}),
                    html.Button('重置', id='reset-btn', n_clicks=0,
                               style={'padding': '4px 12px'}),
                ]),

            ], style={'width': '250px', 'flexShrink': 0, 'padding': '12px',
                      'borderRight': '1px solid #ddd'}),

            # Right: Cytoscape graph
            html.Div([
                cyto.Cytoscape(
                    id='graphrag-cytoscape',
                    elements=initial_elements,
                    stylesheet=make_stylesheet(40, 14, [], [], set(all_rels), G),
                    layout={'name': 'cose', 'animate': True, 'animationDuration': 800, 'padding': 30},
                    style={'width': '100%', 'height': '600px'},
                    zoom=1,
                    pan={'x': 0, 'y': 0},
                    minZoom=0.1,
                    maxZoom=3.0,
                    wheelSensitivity=1,
                    boxSelectionEnabled=True,
                    autounselectify=False,
                ),
            ], style={'flex': 1, 'padding': '12px'}),

        ], style={'display': 'flex', 'flexDirection': 'row', 'border': '1px solid #ddd', 'borderRadius': '8px', 'overflow': 'hidden'}),

        dcc.Store(id='nav-history', data=[]),
        dcc.Store(id='current-selected', data=[]),
        dcc.Store(id='current-visible', data=list(initial_visible)),
    ])

    # ── Callbacks ────────────────────────────────────────────────────────────

    @app.callback(
        Output('graphrag-cytoscape', 'elements'),
        Output('graphrag-cytoscape', 'stylesheet'),
        Output('graphrag-cytoscape', 'layout'),
        Output('nav-history', 'data'),
        Output('current-selected', 'data'),
        Output('current-visible', 'data'),
        Output('current-selection-display', 'children'),
        Output('selection-detail', 'children'),
        Output('selected-chips', 'children'),
        Output('edge-info', 'children'),
        # Inputs
        Input('graphrag-cytoscape', 'tapNodeData'),
        Input('graphrag-cytoscape', 'tapEdgeData'),
        Input('operator-search', 'value'),
        Input('back-btn', 'n_clicks'),
        Input('reset-btn', 'n_clicks'),
        Input('node-size-slider', 'value'),
        Input('text-size-slider', 'value'),
        Input('relation-filter', 'value'),
        # States
        State('nav-history', 'data'),
        State('current-selected', 'data'),
        State('current-visible', 'data'),
        prevent_initial_call=True,
    )
    def update_graph(tap_node_data, tap_edge_data, search_value, back_clicks, reset_clicks,
                     node_size, text_size, visible_rels,
                     history, current_selected, current_visible):

        ctx = callback_context
        if not ctx.triggered:
            raise dash.exceptions.PreventUpdate

        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

        def make_layout():
            return {'name': 'cose', 'animate': True, 'animationDuration': 800, 'padding': 30, 'fit': True}

        # Reset
        if triggered_id == 'reset-btn':
            history = []
            current_selected = []
            init_elems, init_vis = get_initial_elements(G, all_rels)
            stylesheet = make_stylesheet(node_size, text_size, [], [], set(visible_rels), G)
            display = "当前选中：无"
            detail = ""
            chips = html.Span("无", style={'color': '#999', 'fontSize': '11px'})
            edge_info = "点击关系线查看关系类型"
            return init_elems, stylesheet, make_layout(), history, current_selected, list(init_vis), display, detail, chips, edge_info

        # Back
        if triggered_id == 'back-btn':
            if history:
                history = list(history)
                current_selected = history.pop()

                # If nothing selected after back, show all initial nodes
                if not current_selected:
                    init_elems, init_vis = get_initial_elements(G, all_rels)
                    stylesheet = make_stylesheet(node_size, text_size, [], [], set(visible_rels), G)
                    display = "当前选中：无"
                    detail = ""
                    chips = html.Span("无", style={'color': '#999', 'fontSize': '11px'})
                    edge_info = "点击关系线查看关系类型"
                    return init_elems, stylesheet, make_layout(), history, [], list(init_vis), display, detail, chips, edge_info

                neighbors = set()
                for n in current_selected:
                    neighbors.update(G.neighbors(n))
                visible_nodes = set(current_selected) | neighbors
                stylesheet = make_stylesheet(node_size, text_size, current_selected, list(neighbors), set(visible_rels), G)
                elements = build_elements(G, visible_nodes, set(visible_rels))
                display = f"当前选中：{', '.join(current_selected)} ({len(neighbors)} 个相邻)"
                detail = make_detail_html(current_selected, G)
                chips = make_chips(current_selected)
                edge_info = "点击关系线查看关系类型"
                return elements, stylesheet, make_layout(), history, current_selected, list(visible_nodes), display, detail, chips, edge_info
            raise dash.exceptions.PreventUpdate

        # Operator search selection
        if triggered_id == 'operator-search' and search_value:
            if not current_selected:
                current_selected = []
            if history is None:
                history = []

            history = list(history)
            history.append(list(current_selected))

            if search_value in current_selected:
                current_selected = [n for n in current_selected if n != search_value]
            else:
                current_selected = list(current_selected) + [search_value]

            # If nothing selected, show all initial nodes
            if not current_selected:
                init_elems, init_vis = get_initial_elements(G, all_rels)
                stylesheet = make_stylesheet(node_size, text_size, [], [], set(visible_rels), G)
                display = "当前选中：无"
                detail = ""
                chips = html.Span("无", style={'color': '#999', 'fontSize': '11px'})
                edge_info = "点击关系线查看关系类型"
                return init_elems, stylesheet, make_layout(), history, current_selected, list(init_vis), display, detail, chips, edge_info

            neighbors = set()
            for n in current_selected:
                neighbors.update(G.neighbors(n))
            visible_nodes = set(current_selected) | neighbors

            stylesheet = make_stylesheet(node_size, text_size, current_selected, list(neighbors), set(visible_rels), G)
            elements = build_elements(G, visible_nodes, set(visible_rels))
            display = f"当前选中：{', '.join(current_selected)} ({len(neighbors)} 个相邻)"
            detail = make_detail_html(current_selected, G)
            chips = make_chips(current_selected)
            edge_info = "点击关系线查看关系类型"
            return elements, stylesheet, make_layout(), history, current_selected, list(visible_nodes), display, detail, chips, edge_info

        # Edge tap — show relation info, no state change
        if triggered_id == 'graphrag-cytoscape' and tap_edge_data:
            src = tap_edge_data.get('source', '')
            tgt = tap_edge_data.get('target', '')
            rel = tap_edge_data.get('relation', '')
            desc = tap_edge_data.get('description', '')
            edge_info = f"关系：{rel} | {src} → {tgt}"
            if desc:
                edge_info = f"{edge_info} | {desc}"
            visible_nodes = set(current_visible) if current_visible else set()
            stylesheet = make_stylesheet(node_size, text_size, current_selected or [], [], set(visible_rels), G)
            elements = build_elements(G, visible_nodes, set(visible_rels))
            display = f"当前选中：{', '.join(current_selected)}" if current_selected else "当前选中：无"
            detail = make_detail_html(current_selected, G) if current_selected else ""
            chips = make_chips(current_selected) if current_selected else html.Span("无", style={'color': '#999', 'fontSize': '11px'})
            return elements, stylesheet, make_layout(), history, current_selected, list(visible_nodes), display, detail, chips, edge_info

        # Node tap (only if no edge data — edge takes priority)
        if triggered_id == 'graphrag-cytoscape' and tap_node_data and not tap_edge_data:
            node_id = tap_node_data['id']

            if not current_selected:
                current_selected = []
            if history is None:
                history = []

            history = list(history)
            history.append(list(current_selected))

            if node_id in current_selected:
                current_selected = [n for n in current_selected if n != node_id]
            else:
                current_selected = list(current_selected) + [node_id]

            # If nothing selected, show all initial nodes
            if not current_selected:
                init_elems, init_vis = get_initial_elements(G, all_rels)
                stylesheet = make_stylesheet(node_size, text_size, [], [], set(visible_rels), G)
                display = "当前选中：无"
                detail = ""
                chips = html.Span("无", style={'color': '#999', 'fontSize': '11px'})
                edge_info = "点击关系线查看关系类型"
                return init_elems, stylesheet, make_layout(), history, current_selected, list(init_vis), display, detail, chips, edge_info

            neighbors = set()
            for n in current_selected:
                neighbors.update(G.neighbors(n))
            visible_nodes = set(current_selected) | neighbors

            stylesheet = make_stylesheet(node_size, text_size, current_selected, list(neighbors), set(visible_rels), G)
            elements = build_elements(G, visible_nodes, set(visible_rels))
            display = f"当前选中：{', '.join(current_selected)} ({len(neighbors)} 个相邻)"
            detail = make_detail_html(current_selected, G)
            chips = make_chips(current_selected)
            edge_info = "点击关系线查看关系类型"
            return elements, stylesheet, make_layout(), history, current_selected, list(visible_nodes), display, detail, chips, edge_info

        # Node size / text size / relation filter changed
        if triggered_id in ('node-size-slider', 'text-size-slider', 'relation-filter'):
            visible_nodes = set(current_visible) if current_visible else set()
            stylesheet = make_stylesheet(
                node_size,
                text_size,
                current_selected or [],
                [],
                set(visible_rels), G
            )
            elements = build_elements(G, visible_nodes, set(visible_rels))
            display = f"当前选中：{', '.join(current_selected)}" if current_selected else "当前选中：无"
            detail = make_detail_html(current_selected, G) if current_selected else ""
            chips = make_chips(current_selected) if current_selected else html.Span("无", style={'color': '#999', 'fontSize': '11px'})
            edge_info = "点击关系线查看关系类型"
            return elements, stylesheet, make_layout(), history, current_selected, list(visible_nodes), display, detail, chips, edge_info

        raise dash.exceptions.PreventUpdate

    return app

def make_chips(selected_nodes):
    """Build chip components for selected nodes."""
    if not selected_nodes:
        return html.Span("无", style={'color': '#999', 'fontSize': '11px'})
    return [
        html.Span(n, style={
            'backgroundColor': '#FF7043',
            'color': 'white',
            'padding': '2px 8px',
            'borderRadius': '12px',
            'fontSize': '11px',
            'marginRight': '4px',
            'display': 'inline-block',
        })
        for n in selected_nodes
    ]

def make_detail_html(selected_nodes, G):
    """Build HTML detail for selected nodes showing their relations."""
    if not selected_nodes:
        return ""

    items = []
    for node in selected_nodes:
        neighbors = list(G.neighbors(node))
        rel_count = defaultdict(list)
        for nb in neighbors:
            edge_d = G[node][nb]
            rel = edge_d.get('relation', '') or '关系'
            rel_count[rel].append(nb)

        # Node name with degree
        header_parts = [html.Span(node, style={'fontWeight': 'bold'}), "（%d 个关系）：" % len(neighbors)]
        items.append(html.Div(style={'marginBottom': '2px', 'fontSize': '11px'}, children=header_parts))

        for rel, nbs in sorted(rel_count.items()):
            line_parts = [rel, "：", ', '.join(nbs)]
            items.append(html.Div(style={'marginBottom': '2px', 'fontSize': '11px', 'paddingLeft': '12px'}, children=line_parts))

        items.append(html.Hr(style={'margin': '4px 0', 'borderColor': '#eee'}))

    if items:
        items.pop()

    return html.Div(items, style={'fontSize': '11px', 'color': '#444', 'maxHeight': '250px', 'overflowY': 'auto'})


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8050)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()
    print(f"Starting GraphRAG Dashboard on {args.host}:{args.port}...")
    app = create_dash_app()
    app.run(debug=True, host=args.host, port=args.port)
