## 1. Add Multilingual Search Config Support

- [x] 1.1 Add a new optional `search_languages` field to the pipeline config handling and preserve backward compatibility when it is absent
- [x] 1.2 Distinguish `search_languages` from `language_priority` in `src/pipeline.py` and `run_europe_smb.py`
- [x] 1.3 Update query counting, progress reporting, and dedup-safe processing for `city x niche x search_language` expansion

## 2. Add Localized Search Vocabulary

- [x] 2.1 Extend niche configuration data with localized search labels for `nl`, `en`, `es`, `pt`, `de`, `uk`, and `ru`
- [x] 2.2 Implement lookup helpers that resolve localized search phrases from canonical niches
- [x] 2.3 Add fallback behavior so missing translations revert to canonical niche labels instead of failing a run

## 3. Apply Multilingual Discovery To Presets And Runners

- [x] 3.1 Update lead-discovery query generation in `src/pipeline.py` to execute multilingual queries while retaining canonical niche identity
- [x] 3.2 Update `run_europe_smb.py` to use multilingual search phrases and keep query logging coherent per search language
- [x] 3.3 Update `config/run_ukraine_smb.json` so `search_languages` is `["en", "uk", "ru"]`

## 4. Validate And Document

- [x] 4.1 Add tests covering multilingual query generation, vocabulary fallback, and backward compatibility for configs without `search_languages`
- [x] 4.2 Add tests or log assertions verifying query events can distinguish the active search language
- [x] 4.3 Update operator-facing docs to explain supported search languages and the difference between `search_languages` and `language_priority`
