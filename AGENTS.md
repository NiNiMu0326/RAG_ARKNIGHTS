# AGENTS.md

鏈枃浠朵负 Codex (Codex.ai/code) 鍦ㄦ浠ｇ爜搴撲腑宸ヤ綔鏃舵彁渚涙寚瀵笺€?
## 椤圭洰姒傝堪

鏄庢棩鏂硅垷 ARKNIGHTS Agent 闂瓟绯荤粺銆備竴涓?AI Agent锛岄€氳繃 Function Calling 鑷富鍐冲畾妫€绱㈣矾寰勶細鐭ヨ瘑搴撴绱€佺煡璇嗗浘璋辨煡璇€佺綉缁滄悳绱紝涓変釜宸ュ叿鍙苟琛岃皟鐢ㄣ€傛敮鎸?SSE 娴佸紡杈撳嚭銆佺敤鎴疯璇侊紙JWT锛夈€佷細璇濇寔涔呭寲锛圫QLite锛夈€佸 LLM 妯″瀷鍒囨崲銆?
鏈」鐩凡绉婚櫎鏃х殑 PipelineRAG 鏋舵瀯锛屾墍鏈?RAG 鍔熻兘閫氳繃 Agent 宸ュ叿璋冪敤瀹炵幇锛屼笉瀛樺湪鐙珛鐨勬煡璇㈡敼鍐?CRAG/绛旀鐢熸垚姝ラ銆?
## 鏈嶅姟鍣?
- **鍦板潃**锛?19.147.202.190:14602
- **SSH**锛歚ssh root@119.147.202.190 -p 14602`
- **瀵嗙爜**锛歀Lll11..
- **椤圭洰璺緞**锛氭湇鍔″櫒涓婇」鐩綅浜?`/root/ARKNIGHTS_AgenticRAG/`锛堟垨绫讳技璺緞锛?
## 鏋舵瀯

### Agent 涓诲惊鐜紙`backend/agent/core.py`锛?
```
鐢ㄦ埛娑堟伅 鈫?build_messages() 鈫?LLM(FC) 鈫?tool_calls? 鈫?骞惰鎵ц 鈫?缁撴灉娉ㄥ叆 鈫?缁х画寰幆
                                                    鈫?鏃?tool_calls
                                              娴佸紡杈撳嚭鍥炵瓟 鈫?缁撴潫
```

姣忚疆 LLM 杩斿洖宸ュ叿璋冪敤鏃跺苟琛屾墽琛岋紝缁撴灉鍔犲叆娑堟伅鍘嗗彶缁х画涓嬩竴杞紝鐩村埌妯″瀷璁や负淇℃伅鍏呰冻鎴栬揪鍒?max_rounds=8 涓婇檺銆?
### 涓変釜宸ュ叿锛坄backend/agent/tool_implementations.py`锛?
| 宸ュ叿 | 鍔熻兘 | 娴佺▼ |
|------|------|------|
| `arknights_rag_search` | 鐭ヨ瘑搴撴绱?| FAISS + BM25 鈫?RRF 铻嶅悎 鈫?Cross-Encoder 閲嶆帓 鈫?Parent Document 鎵╁睍 |
| `arknights_graphrag_search` | 鐭ヨ瘑鍥捐氨鏌ヨ | 鍗曞疄浣撻偦灞呮煡璇?/ 鍙屽疄浣撴渶鐭矾寰勬煡鎵?|
| `web_search` | 缃戠粶鎼滅储 | Tavily API + DuckDuckGo 鍏滃簳 |

宸ュ叿閫氳繃 `ToolRegistry` 娉ㄥ唽锛孲chema 瀹氫箟鍦?`tools.py`锛屽疄鐜板湪 `tool_implementations.py`銆?
### 瀹夊叏鏈哄埗

- max_rounds=8 纭檺鍒?- `detect_loop()` 寰幆妫€娴嬶紙鏈€杩?3 杞浉鍚?tool_calls 鍗崇粓姝級
- LLM 鏈€澶ц緭鍑?token 闄愬埗

### LLM 澶氭ā鍨嬶紙`backend/api/llm_factory.py`锛?
鎵€鏈?Provider 閫氳繃 OpenAI 鍏煎 API 缁熶竴锛屽簳灞傚鐢?`DeepSeekClient`锛堝垏鎹?base_url/api_key/model锛夈€?
| model_id | Provider | 鏄剧ず鍚嶇О |
|----------|----------|----------|
| `deepseek-chat` | DeepSeek | DeepSeek-V4-Flash (DeepSeek瀹樻柟) |
| `minimax-m2.7` | MiniMax | MiniMax-M2.7 |

榛樿妯″瀷锛歚minimax-m2.7`

### 浼氳瘽绠＄悊锛坄backend/agent/sessions.py`锛?
- TTL 3600 绉掞紝鏈€澶?1000 浼氳瘽锛孡RU 椹遍€?- 绾跨▼瀹夊叏锛坅syncio.Lock锛?- 鍓嶇 Pinia sessions store 鍚屾绠＄悊锛屾敮鎸?localStorage + 鏈嶅姟绔弻閲嶆寔涔呭寲

## 鏂囦欢娓呭崟

### Agent 鏍稿績锛坄backend/agent/`锛?
| 鏂囦欢 | 鑱岃矗 |
|------|------|
| `core.py` | Agent 涓诲惊鐜細SSE 娴佸紡銆佸苟琛?Function Calling銆佸惊鐜娴嬨€佹秷鎭瀯寤?|
| `tools.py` | 涓変釜宸ュ叿鐨?Schema 瀹氫箟 + ToolRegistry 娉ㄥ唽琛?|
| `tool_implementations.py` | 涓変釜宸ュ叿鐨勫疄闄呭疄鐜?+ BM25/GraphBuilder 鎳掑姞杞藉崟渚?|
| `sessions.py` | 浼氳瘽绠＄悊锛氬垱寤恒€佹煡璇€乀TL 杩囨湡銆丩RU 椹遍€愩€佺嚎绋嬪畨鍏?|
| `prompts.py` | 绯荤粺鎻愮ず璇嶆ā鏉?+ build_messages() 娑堟伅涓婁笅鏂囨瀯寤?|

### API 瀹㈡埛绔紙`backend/api/`锛?
| 鏂囦欢 | 鑱岃矗 |
|------|------|
| `llm_factory.py` | 澶?Provider LLM 宸ュ巶锛屾ā鍨嬪垪琛ㄣ€佸垱寤哄鎴风 |
| `deepseek.py` | OpenAI 鍏煎瀹㈡埛绔細Chat Completion + Function Calling + SSE 娴佸紡 |
| `siliconflow.py` | SiliconFlow API锛氬祵鍏ワ紙bge-m3锛夈€侀噸鎺掞紙bge-reranker-v2-m3锛夈€丩LM |
| `web_search.py` | 缃戠粶鎼滅储锛歍avily API 浼樺厛锛孌uckDuckGo HTML 瑙ｆ瀽鍏滃簳 |

### RAG 鍩虹璁炬柦锛坄backend/rag/`锛?
| 鏂囦欢 | 鑱岃矗 |
|------|------|
| `retrievers.py` | 澶氶€氶亾妫€绱細FAISS 鍚戦噺 + BM25 鍏抽敭璇?鈫?RRF 铻嶅悎锛岀粨鏋滅紦瀛?5h |
| `parent_document.py` | Parent Document 鎵╁睍锛氭绱㈠埌鐨?chunk 鈫?瀵瑰簲鐖舵枃妗ｏ紝LRU 缂撳瓨 max 100 |
| `alias_map.py` | 骞插憳鍒悕鏄犲皠瀛楀吀锛屼緵 `/quick-questions` API 浣跨敤 |
| `graphrag/builder.py` | 鐭ヨ瘑鍥捐氨鏋勫缓锛氫粠 entity_relations.json 鏋勫缓 NetworkX DiGraph |
| `graphrag/extractor.py` | 瀹炰綋鍏崇郴鎻愬彇 |
| `graphrag/query.py` | 鍥捐氨鏌ヨ鍗曚緥锛坓et_graph_builder锛夛細閭诲眳鏌ヨ + 鏈€鐭矾寰勬煡鎵?|

### LangChain 灏佽锛坄backend/lc/`锛?
| 鏂囦欢 | 鑱岃矗 |
|------|------|
| `embeddings.py` | LangChain Embeddings 灏佽锛岃 retrievers.py 鍜?tool_implementations.py 浣跨敤 |
| `reranker.py` | LangChain Cross-Encoder Reranker 灏佽锛岃 tool_implementations.py 浣跨敤 |

### 鍩虹璁炬柦锛坄backend/`锛?
| 鏂囦欢 | 鑱岃矗 |
|------|------|
| `main.py` | FastAPI 涓诲簲鐢細鎵€鏈夎矾鐢便€丼SE 绔偣銆丆ORS銆侀潤鎬佹枃浠舵寕杞?|
| `config.py` | 鍏ㄥ眬閰嶇疆锛欰PI Keys銆佹ā鍨嬪弬鏁般€佽矾寰勫父閲?|
| `db.py` | SQLite 鏁版嵁搴擄紙aiosqlite锛夛細鐢ㄦ埛琛ㄣ€佷細璇濊〃鍒濆鍖?|
| `auth.py` | JWT 璁よ瘉锛氭敞鍐屻€佺櫥褰曘€乼oken 绛惧彂/楠岃瘉銆佸瘑鐮佸搱甯?|
| `storage/faiss_client.py` | FAISS 鍚戦噺绱㈠紩灏佽锛氬姞杞姐€佹悳绱€佹寔涔呭寲鍒?`faiss_index/` |

### 鏁版嵁鑴氭湰锛坄backend/data/`锛?
| 鏂囦欢 | 鑱岃矗 |
|------|------|
| `chunker.py` | 鏂囨湰鍒囧潡锛氬皢鍘熷鏁版嵁鍒囨垚妫€绱㈢敤 chunk |
| `bm25_index.py` | BM25 鍏抽敭璇嶇储寮曟瀯寤?|

### 鍓嶇锛坄frontend/src/`锛?
**椤甸潰锛坴iews/锛夛細**
| 鏂囦欢 | 璺敱 | 鍔熻兘 |
|------|------|------|
| `ChatView.vue` | `/chat` | 闂瓟鐣岄潰锛歋SE 娴佸紡瀵硅瘽銆佸伐鍏疯皟鐢ㄥ崱鐗囥€佹€濊€冭繃绋嬪睍寮€銆佸揩鎹烽棶棰樻寜閽€佹秷鎭槦鍒?|
| `AdminView.vue` | `/admin` | 绠＄悊闈㈡澘锛欳hunk 娴忚鍣紙鎸夐泦鍚堟祻瑙?鎼滅储鍒囧潡锛夈€佹暟鎹华琛ㄦ澘锛堢粺璁″浘琛級 |
| `GraphView.vue` | `/graph` | 浜や簰寮忕煡璇嗗浘璋憋細Cytoscape.js 鍔涘鍚戝竷灞€銆佽妭鐐规悳绱€侀偦灞呭睍寮€銆佸叧绯荤瓫閫?|

**缁勪欢锛坈omponents/锛夛細**
| 鏂囦欢 | 鍔熻兘 |
|------|------|
| `AppSidebar.vue` | 渚ц竟鏍忥細瀵艰埅 + 浼氳瘽鍒楄〃绠＄悊 + 鍥捐氨鎺у埗闈㈡澘锛堟悳绱€侀€夋嫨銆佸叧绯荤瓫閫夛級 |
| `AppHeader.vue` | 椤堕儴鏍忥細绉诲姩绔彍鍗曟寜閽?+ 椤甸潰鏍囬 + 璁剧疆鍏ュ彛 |
| `AuthModal.vue` | 鐧诲綍/娉ㄥ唽寮圭獥 |
| `SettingsModal.vue` | 璁剧疆寮圭獥锛氳处鎴蜂俊鎭?淇敼瀵嗙爜銆佷富棰樺垏鎹€佹ā鍨嬮€夋嫨銆佸叧浜?|
| `Toast.vue` | 鍏ㄥ眬閫氱煡鎻愮ず |

**鐘舵€佺鐞嗭紙stores/锛夛細**
| 鏂囦欢 | 鑱岃矗 |
|------|------|
| `sessions.js` | 浼氳瘽 CRUD銆佹秷鎭鐞嗐€乴ocalStorage/鏈嶅姟绔悓姝?|
| `auth.js` | JWT token 绠＄悊銆佺敤鎴风姸鎬併€佺櫥褰?娉ㄥ唽/鐧诲嚭 |
| `settings.js` | 涓婚鍒囨崲銆佹ā鍨嬮€夋嫨銆佽缃寔涔呭寲 |
| `quickQuestions.js` | 蹇嵎闂缂撳瓨 |
| `toast.js` | 閫氱煡娑堟伅 |

**鍏朵粬锛?*
| 鏂囦欢 | 鑱岃矗 |
|------|------|
| `api.js` | API 瀹㈡埛绔細鎵€鏈夊悗绔帴鍙ｅ皝瑁咃紝鍚?`agentChat()` SSE 娴佸紡璋冪敤 |
| `composables/useGraphController.js` | 鍥捐氨鎺у埗鍣ㄥ崟渚嬶紝GraphView 鍜?AppSidebar 鍏变韩 |
| `assets/styles.css` | 鍏ㄥ眬鏍峰紡锛圕SS 鍙橀噺銆佸弻涓婚銆佺粍浠舵牱寮忥級 |
| `assets/graphrag.css` | 鐭ヨ瘑鍥捐氨涓撶敤鏍峰紡 |

### 鏁版嵁鐩綍

| 璺緞 | 鍐呭 |
|------|------|
| `data/` | 鍘熷鏁版嵁闆嗭紙JSON/Markdown锛夛細骞插憳鏁版嵁銆佹晠浜嬨€佺煡璇嗙瓑 |
| `chunks/` | 鏂囨湰鍒囧潡杈撳嚭锛屾寜 collection 鍒嗙洰褰?|
| `chunks/graphrag/entity_relations.json` | 鐭ヨ瘑鍥捐氨瀹炰綋鍏崇郴鏁版嵁 |
| `faiss_index/` | FAISS 鍚戦噺绱㈠紩鎸佷箙鍖栨枃浠?|

## API 绔偣

### Agent
| 鏂规硶 | 璺緞 | 鎻忚堪 |
|------|------|------|
| POST | `/agent/chat` | Agent SSE 娴佸紡瀵硅瘽锛堟牳蹇冪鐐癸級 |
| POST | `/agent/session` | 鍒涘缓浼氳瘽锛岃繑鍥?session_id |
| GET | `/agent/session/{id}/messages` | 鑾峰彇浼氳瘽娑堟伅鍘嗗彶 |
| DELETE | `/agent/session/{id}` | 鍒犻櫎浼氳瘽 |
| GET | `/agent/models` | 鍙敤 LLM 妯″瀷鍒楄〃 |
| GET | `/agent/stats` | 浼氳瘽缁熻 |

### 璁よ瘉
| 鏂规硶 | 璺緞 | 鎻忚堪 |
|------|------|------|
| POST | `/auth/register` | 娉ㄥ唽锛坲sername, account, password锛?|
| POST | `/auth/login` | 鐧诲綍锛坅ccount, password锛夛紝杩斿洖 JWT token |
| GET | `/auth/me` | 褰撳墠鐢ㄦ埛淇℃伅 |
| POST | `/auth/change-password` | 淇敼瀵嗙爜 |

### 浼氳瘽绠＄悊
| 鏂规硶 | 璺緞 | 鎻忚堪 |
|------|------|------|
| GET | `/conversations` | 鐢ㄦ埛浼氳瘽鍒楄〃 |
| GET | `/conversations/{id}/messages` | 浼氳瘽娑堟伅 |
| POST | `/conversations/sync` | 鍚屾鏈湴浼氳瘽鍒版湇鍔＄ |
| DELETE | `/conversations/{id}` | 鍒犻櫎浼氳瘽 |
| PUT | `/conversations/{id}/rename` | 閲嶅懡鍚嶄細璇?|

### 鏁版嵁
| 鏂规硶 | 璺緞 | 鎻忚堪 |
|------|------|------|
| GET | `/health` | 鍋ュ悍妫€鏌?|
| GET | `/status` | 閰嶇疆鐘舵€侊紙妯″瀷銆丄PI 鍙敤鎬э級 |
| GET | `/stats` | 鏁版嵁缁熻锛堝共鍛樻暟銆佹晠浜嬫暟銆佺煡璇嗘暟銆佸浘璋辫妭鐐?杈规暟锛?|
| GET | `/chunks/{collection}` | 鎸囧畾闆嗗悎鐨勫垏鍧楀垪琛?|
| GET | `/chunks/{collection}/{id}` | 鍗曚釜鍒囧潡璇︽儏 |
| GET | `/knowledge-graph` | 鐭ヨ瘑鍥捐氨瀹屾暣鏁版嵁锛坋ntities + relations锛?|
| GET | `/quick-questions` | 蹇嵎闂鍒楄〃 |
| GET | `/operators` | 骞插憳鍒楄〃 |
| GET | `/characters` | 瑙掕壊鍒楄〃 |
| GET | `/stories` | 鏁呬簨鍒楄〃 |

瀹屾暣璺敱瀹氫箟瑙?`backend/main.py`銆?
## 鐜鍙橀噺锛坄backend/.env`锛?
| 鍙橀噺 | 蹇呴』 | 璇存槑 |
|------|------|------|
| `SILICONFLOW_API_KEY` | 鏄?| 宓屽叆锛坆ge-m3锛? 閲嶆帓锛坆ge-reranker-v2-m3锛? 榛樿 LLM |
| `JWT_SECRET` | 鏄?| JWT 绛惧悕瀵嗛挜锛屼笉璁剧疆鍒欐湇鍔℃嫆缁濆惎鍔?|
| `DEEPSEEK_API_KEY_2` | 鍚?| DeepSeek 瀹樻柟妯″瀷 API Key |
| `TAVILY_API_KEY` | 鍚?| Tavily 缃戠粶鎼滅储锛屼笉濉垯 DuckDuckGo 鍏滃簳 |
| `MINIMAX_API_KEY` | 鍚?| MiniMax M2.7 妯″瀷 |
| `PORT` | 鍚?| 鍚庣绔彛锛岄粯璁?8100 |

## 寮€鍙戞敞鎰忎簨椤?
- **绔彛**锛氬悗绔?8100锛屽墠绔紑鍙戞湇鍔″櫒 5300锛圴ite 浠ｇ悊杞彂 API 鍒?8100锛?- Agent 浣跨敤 DeepSeek Function Calling锛?*涓嶈浼?`parallel_tool_calls` 鍙傛暟**锛堜細浣垮叾鏇翠繚瀹堬級
- GraphRAG 浣跨敤 `nx.DiGraph`锛堟湁鍚戝浘锛夛紝浣嗚矾寰勬煡鎵炬椂杞负鏃犲悜瑙嗗浘
- BM25 绱㈠紩鍜?GraphBuilder 閲囩敤鎳掑姞杞藉崟渚嬫ā寮忥紙绾跨▼瀹夊叏锛?- FAISS 鍚戦噺鏁版嵁鎸佷箙鍖栧埌 `faiss_index/` 鐩綍
- GraphRAG 瀹炰綋鍏崇郴鏁版嵁鍦?`chunks/graphrag/entity_relations.json`
- 鍓嶇 Vite 浠ｇ悊閰嶇疆灏嗘墍鏈?`/agent`銆乣/auth`銆乣/conversations` 绛夎矾寰勮浆鍙戝埌鍚庣

### SSE 浜嬩欢绫诲瀷

Agent 娴佸紡瀵硅瘽浣跨敤浠ヤ笅 SSE 浜嬩欢锛屾寜鏃堕棿椤哄簭锛?
| 浜嬩欢 | 鍚箟 |
|------|------|
| `thinking_start` | 寮€濮嬫柊涓€杞€濊€?|
| `thinking_delta` | 鎬濊€冭繃绋嬪閲忔枃鏈?|
| `tool_calls_start` | 妯″瀷鍐冲畾璋冪敤宸ュ叿 |
| `tool_executing` | 姝ｅ湪鎵ц鏌愪釜宸ュ叿锛堝惈宸ュ叿鍚嶅拰鍙傛暟锛?|
| `tool_call_result` | 宸ュ叿鎵ц瀹屾垚锛堝惈杩斿洖缁撴灉锛?|
| `answer_delta` | 鏈€缁堝洖绛旀祦寮忓閲?|
| `answer_done` | 鍥炵瓟瀹屾垚锛堝惈鎬昏疆鏁般€佽€楁椂锛?|
| `error` | 鍑洪敊 |

### 鎶€鏈爤

| 缁勪欢 | 鎶€鏈?|
|------|------|
| 鍚庣妗嗘灦 | FastAPI + Uvicorn |
| Agent LLM | DeepSeek-V4-Flash / MiniMax-M2.7 |
| 鍚戦噺鏁版嵁搴?| FAISS锛堝唴瀛樼储寮?+ 纾佺洏鎸佷箙鍖栵級 |
| 宓屽叆妯″瀷 | BAAI/bge-m3锛圫iliconFlow API锛?|
| 閲嶆帓妯″瀷 | BAAI/bge-reranker-v2-m3锛圫iliconFlow API锛?|
| 缃戠粶鎼滅储 | Tavily API + DuckDuckGo |
| 鐭ヨ瘑鍥捐氨 | NetworkX DiGraph |
| 鏁版嵁搴?| SQLite锛坅iosqlite 寮傛锛?|
| 鍓嶇妗嗘灦 | Vue 3锛圕omposition API + script setup锛?|
| 鐘舵€佺鐞?| Pinia |
| 鏋勫缓宸ュ叿 | Vite 5 |
| 鍥捐氨鍙鍖?| Cytoscape.js |

### 鍚姩鍛戒护

```bash
# 鍚庣
cd backend && uvicorn main:app --host 0.0.0.0 --port 8100

# 鍓嶇寮€鍙?cd frontend && npm run dev

# 鏋勫缓绱㈠紩锛堥娆′娇鐢級
python backend/data/chunker.py
python backend/data/bm25_index.py
python backend/build_faiss_index.py
```
## 部署工作流

本项目采用 **本地开发 → Git 推送 → 服务器拉取** 的工作流：

1. **本地开发**：在本地 `D:\Agent\ARKNIGHTSAgent` 修改代码
2. **Git 提交推送**：使用 `git add` + `git commit` + `git push` 推送到远程仓库
3. **服务器部署**：SSH 登录服务器执行 `git pull` 拉取最新代码

### 服务器信息
- **地址**：119.147.202.190:14602
- **SSH**：`ssh root@119.147.202.190 -p 14602`
- **密码**：LLll11..
- **项目路径**：`/root/ARKNIGHTS_AgenticRAG/`

### 部署命令示例

```bash
# 本地提交并推送
git add -A
git commit -m "[feat] 描述改动内容"
git push origin main

# 服务器拉取更新
ssh root@119.147.202.190 -p 14602
cd /root/ARKNIGHTS_AgenticRAG/
git pull
```

### 注意事项
- 每次重要改动后必须 commit，commit message 使用中文描述
- 推送到仓库后提醒用户到服务器执行 `git pull`
- 服务器上可能需要重启服务才能生效（如 uvicorn）


<!-- gitnexus:start -->
# GitNexus 鈥?Code Intelligence

This project is indexed by GitNexus as **RAG_ARKNIGHTS_LangChain** (1972 symbols, 3495 relationships, 56 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol 鈥?callers, callees, which execution flows it participates in 鈥?use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` 鈥?find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` 鈥?see all callers, callees, and process participation
3. `READ gitnexus://repo/RAG_ARKNIGHTS_LangChain/process/{processName}` 鈥?trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` 鈥?see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview 鈥?graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace 鈥?use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK 鈥?direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED 鈥?indirect deps | Should test |
| d=3 | MAY NEED TESTING 鈥?transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/RAG_ARKNIGHTS_LangChain/context` | Codebase overview, check index freshness |
| `gitnexus://repo/RAG_ARKNIGHTS_LangChain/clusters` | All functional areas |
| `gitnexus://repo/RAG_ARKNIGHTS_LangChain/processes` | All execution flows |
| `gitnexus://repo/RAG_ARKNIGHTS_LangChain/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` 鈥?the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Codex users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.Codex/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.Codex/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.Codex/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.Codex/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.Codex/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.Codex/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

