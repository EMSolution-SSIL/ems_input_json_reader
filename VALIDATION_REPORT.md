# EMSolution input.json 検証レポート

検証対象: `C:\EMSolution\build\reader_json_files\data` の JSON 255件。各ファイルの診断と判定は `build/corpus_report.json` に記録する。再実行:

```powershell
python tests/run_corpus.py --root ../reader_json_files --report build/corpus_report.json
```

| 判定 | 件数 | 意味 |
| --- | ---: | --- |
| `full` | 0 | チェッカーの対象項目をすべて検証済み |
| `incomplete` | 255 | 確定エラーなし。チェッカーに未検証の項目が残る |
| `error` / `unreadable` | 0 | 確定した設定エラー／読み込みエラーなし |

`14_Periodic_Boundary_Conditions.PERIODIC_CONDITION[].CYCLIC=0` は、ユーザーの説明に基づき「周期境界条件なし」を示す手入力のプレースホルダーとして受け入れる。通常は `14_Periodic_Boundary_Conditions` キーを省略する。0の行は周期境界の検証対象から外し、`INACTIVE_PERIODIC` 警告だけを記録する。値1～5の周期条件は従来どおり検査し、6などの範囲外はエラーにする。この許容は現行C/C++の `src/boundary/boundary_cond.c:339` にある厳密な1～5の条件より広い、チェッカー固有の扱いである。

該当する2ファイル:

- `010_FieldSource/010_PeriodicBoundaryConditions/020_HoleConductor/input1.json`
- `190_Electrostatic/020_3PhaseLines/input1.json`

入力に対応する出力ファイルが、相対フォルダと番号の命名規則では見つからないものが15件ある。この対応関係は入力の設定判定に影響しない。

結論: 255件に確定した設定エラーはない。全件の `incomplete` は材料・ソース・時間条件などチェッカーに未実装の検証が残ることを示す。各項目の診断はJSONレポートを参照。本コーパスによる互換性検証を終了する。
