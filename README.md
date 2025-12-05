# Транслятор учебного конфигурационного языка в JSON

### Запуск

```bash
python main.py --input config.txt --output result.json
```

**Параметры:**
- `--input, -i` — путь к входному файлу конфигурации (обязателен)
- `--output, -o` — путь к выходному JSON-файлу (обязателен)

### Пример

**Входной файл (config.txt):**
```
REM пример конфигурации

(def port 8080);
(def host 'localhost');

--[[
многострочный
комментарий
]]
(def server struct {
    name = 'main',
    address = struct {
        host = .(host).,
        port = .(port).
    },
    enabled = 1
});
```

**Команда:**
```bash
python3 main.py -i config.txt -o result.json
```

**Выходной файл (result.json):**
```json
{
  "port": 8080,
  "host": "localhost",
  "server": {
    "name": "main",
    "address": {
      "host": "localhost",
      "port": 8080
    },
    "enabled": 1
  }
}
```
