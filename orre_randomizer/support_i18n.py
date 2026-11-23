"""Offline diagnostic-export copy in the six supported interface languages."""

ROWS = {
    "Exporter un diagnostic…": ("Export diagnostic…", "Diagnose exportieren…", "Exportar diagnóstico…", "Esporta diagnostica…", "診断情報をエクスポート…"),
    "Exporter un diagnostic": ("Export diagnostic", "Diagnose exportieren", "Exportar diagnóstico", "Esporta diagnostica", "診断情報のエクスポート"),
    "Le fichier contient la version, le jeu, les réglages et, si vous l’incluez, la seed. L’erreur est résumée par un code.": (
        "The file contains the version, game, settings and, if included, the seed. Errors are represented by a code.",
        "Die Datei enthält Version, Spiel, Einstellungen und optional den Seed. Fehler werden durch einen Code dargestellt.",
        "El archivo contiene la versión, el juego, los ajustes y, si la incluyes, la semilla. El error se resume con un código.",
        "Il file contiene versione, gioco, impostazioni e, se incluso, il seed. Gli errori sono riassunti con un codice.",
        "バージョン、ゲーム、設定と、含める場合はシードを保存します。エラーはコードで記録されます。"),
    "Les chemins locaux, ROM, sauvegardes et journaux sont exclus. Rien n’est envoyé automatiquement.": (
        "Local paths, ROMs, saves and logs are excluded. Nothing is sent automatically.",
        "Lokale Pfade, ROMs, Spielstände und Protokolle sind ausgeschlossen. Es wird nichts automatisch gesendet.",
        "Se excluyen las rutas locales, ROM, partidas guardadas y registros. No se envía nada automáticamente.",
        "Percorsi locali, ROM, salvataggi e registri sono esclusi. Nulla viene inviato automaticamente.",
        "ローカルパス、ROM、セーブデータ、ログは含まれません。自動送信は行いません。"),
    "Contexte": ("Context", "Kontext", "Contexto", "Contesto", "対象"),
    "Contexte du diagnostic": ("Diagnostic context", "Diagnosekontext", "Contexto del diagnóstico", "Contesto della diagnostica", "診断対象"),
    "Dernier échec": ("Last failed operation", "Letzter fehlgeschlagener Vorgang", "Última operación fallida", "Ultima operazione non riuscita", "最後に失敗した操作"),
    "Réglages actuels": ("Current settings", "Aktuelle Einstellungen", "Ajustes actuales", "Impostazioni attuali", "現在の設定"),
    "Inclure la seed": ("Include seed", "Seed einschließen", "Incluir semilla", "Includi seed", "シードを含める"),
    "Relisez la seed avant de partager ce fichier. Elle peut contenir du texte personnel.": (
        "Review the seed before sharing this file. It may contain personal text.",
        "Prüfe den Seed vor dem Teilen. Er kann persönlichen Text enthalten.",
        "Revisa la semilla antes de compartir este archivo. Puede contener texto personal.",
        "Controlla il seed prima di condividere il file. Può contenere testo personale.",
        "共有する前にシードを確認してください。個人的な内容が含まれている場合があります。"),
    "Seed non incluse : elle est invalide ou ressemble à une information privée. Vous pouvez la communiquer séparément si nécessaire.": (
        "Seed omitted: it is invalid or looks like private information. You can share it separately if needed.",
        "Seed nicht enthalten: Er ist ungültig oder ähnelt privaten Angaben. Du kannst ihn bei Bedarf separat mitteilen.",
        "Semilla omitida: no es válida o parece contener información privada. Puedes compartirla por separado si hace falta.",
        "Seed omesso: non è valido o sembra contenere informazioni private. Se necessario, puoi condividerlo separatamente.",
        "シードは無効か個人情報の可能性があるため省略しました。必要な場合は別途共有できます。"),
    "Contenu du diagnostic": ("Diagnostic contents", "Diagnoseinhalt", "Contenido del diagnóstico", "Contenuto della diagnostica", "診断情報の内容"),
    "Enregistrer le diagnostic…": ("Save diagnostic…", "Diagnose speichern…", "Guardar diagnóstico…", "Salva diagnostica…", "診断情報を保存…"),
    "Enregistrer le diagnostic": ("Save diagnostic", "Diagnose speichern", "Guardar diagnóstico", "Salva diagnostica", "診断情報を保存"),
    "Diagnostic enregistré. Joignez ce fichier à votre signalement.": (
        "Diagnostic saved. Attach this file to your bug report.",
        "Diagnose gespeichert. Hänge diese Datei an deinen Fehlerbericht an.",
        "Diagnóstico guardado. Adjunta este archivo a tu informe del problema.",
        "Diagnostica salvata. Allega il file alla segnalazione del problema.",
        "診断情報を保存しました。不具合報告にこのファイルを添付してください。"),
    "Enregistrement du diagnostic…": ("Saving diagnostic…", "Diagnose wird gespeichert…", "Guardando diagnóstico…", "Salvataggio diagnostica…", "診断情報を保存中…"),
    "Diagnostic trop volumineux. Vérifiez les réglages et réessayez.": (
        "Diagnostic too large. Check the settings and try again.", "Diagnose zu groß. Prüfe die Einstellungen und versuche es erneut.",
        "El diagnóstico es demasiado grande. Revisa los ajustes e inténtalo de nuevo.", "Diagnostica troppo grande. Controlla le impostazioni e riprova.",
        "診断情報が大きすぎます。設定を確認してやり直してください。"),
    "Choisissez un fichier JSON pour le diagnostic.": (
        "Choose a JSON file for the diagnostic.", "Wähle eine JSON-Datei für die Diagnose.", "Elige un archivo JSON para el diagnóstico.",
        "Scegli un file JSON per la diagnostica.", "診断情報にはJSONファイルを選択してください。"),
}

TEXTS = {code: {key: values[index] for key, values in ROWS.items()}
         for index, code in enumerate(("en", "de", "es", "it", "ja"))}
