# EMSolution input.json チェッカー

EMSolution の `input.json` を、EMSolution 本体を起動せずに確認する、ソース公開の独立した Python プロジェクトです。判定ルールは `EMSolBuild_VS2022/src@52d71bd` の C/C++ 読込処理を根拠にしています。入力ファイルは変更しません。

[English README](README.md)

## インストール

Python 3.10 以降を用意し、このフォルダで実行します。実行時の外部依存パッケージはありません。[GitHub Releases](https://github.com/EMSolution-SSIL/ems_input_json_reader/releases)にも wheel を置きます。

```powershell
python -m pip install -e .
```

## 使い方

```powershell
emso-check-input C:\path\to\input.json
emso-check-input C:\path\to\input.json --format json --output check-result.json
python -m emso_input_checker C:\path\to\input.json
```

終了コードは、`0` が検査済みで問題なし、`1` が確定した設定エラー、`2` が未検査部分あり、`3` がファイル・JSON 構文・コマンドの失敗です。診断には JSON 内の位置と根拠となる C/C++ ソースを表示します。

共通節の型・値域、解析方式による分岐、数値式、一部の入れ子の項目、時間関数や BH 曲線の参照を確認します。材料、磁界源、運動、メッシュに依存する条件、任意節の一部には未検査の詳細があり、`incomplete` と表示します。未対応の数値式を Python コードとして実行することはありません。

`--check-files` を指定しても、形式番号だけでは外部メッシュファイル名を確定できません。その場合は未検査として報告します。

ご提供のモータと IronCoil の例では、確定した設定エラーはありませんでした。未検査部分があるため、両方とも終了コード `2` です。これらの解析モデルは本プロジェクトに含めていません。テストは合成した入力を使います。

## テストと wheel

```powershell
python -m unittest discover -s tests -v
python -m pip wheel . --no-deps -w dist
```

検査範囲と残作業は[実装計画書](INPUT_JSON_CHECKER_PLAN.md)で確認できます。

## ライセンス

PolyForm Perimeter License 1.0.1。[LICENSE](LICENSE) と [NOTICE](NOTICE) を参照してください。ライセンスの範囲で利用・改変できますが、競合する input チェッカーを他者に提供する用途は制限されます。ソース公開のプロジェクトであり、OSI 定義の OSS ではありません。

## 検証用 JSON 群の一括テスト

独立した `../reader_json_files/data` の入力 JSON 255件を、次のコマンドで再検査できます。

```powershell
python tests/run_corpus.py --root ../reader_json_files --report build/corpus_report.json
```

スクリプトはファイルごとの判定を JSON レポートに保存します。終了コードは全件検証済みなら 0、確定した設定エラーがあれば 1、未検証の設定だけが残れば 2、ファイルの読み込みまたは実行に失敗したら 3 です。未検証を許容する場合は `--allow-incomplete` を指定できます。実データはパッケージに含めません。

255件すべてにチェッカーの未検証項目が残りますが、確定した設定エラーは0件です。2件の `14_Periodic_Boundary_Conditions.PERIODIC_CONDITION[0].CYCLIC=0` は、ユーザーの説明に基づいて「周期境界条件なし」のプレースホルダーとして受け入れ、警告を記録します。通常はセクション自体を省略します。これは現行C/C++コードの厳密な1～5の条件より広い扱いです。命名規則上、対応する出力ファイルがない入力は15件で、入力の判定には影響しません。詳細は[検証レポート](VALIDATION_REPORT.md)を参照してください。
