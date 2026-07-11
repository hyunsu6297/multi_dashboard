param(
  [string]$BlpHost = "localhost",
  [int]$BlpPort = 8194
)

$ErrorActionPreference = "Stop"

try {
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}

$fields = [ordered]@{
  CUR_MKT_CAP = "marketCap"
  TURNOVER_AVG_3M = "avgTurnover3m"
  VOLUME_AVG_3M = "avgVolume3m"
  PX_LAST = "price"
  PX_PREV_CLOSE = "prevClose"
  CHG_PCT_1D = "change"
}

function Write-JsonAndExit($payload, [int]$code) {
  $payload | ConvertTo-Json -Depth 20 -Compress
  exit $code
}

try {
  $rawInput = [Console]::In.ReadToEnd()
  $payload = if ($rawInput.Trim()) { $rawInput | ConvertFrom-Json } else { [pscustomobject]@{ securities = @() } }
  $requested = @($payload.securities) | ForEach-Object { [string]$_ } | Where-Object { $_.Trim() } | Select-Object -Unique
  $allSecurities = @($requested) + @("USDKRW Curncy") | Select-Object -Unique

  $dllCandidates = @(
    "C:\blp\API\Office Tools\Bloomberglp.Blpapi.dll",
    "C:\blp\Wintrv\ttlsupd64\Bloomberglp.Blpapi.dll"
  )
  $dll = $dllCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
  if (-not $dll) {
    throw "Bloomberglp.Blpapi.dll was not found under C:\blp."
  }

  $dapi = "C:\blp\DAPI"
  if (Test-Path -LiteralPath $dapi) {
    $env:PATH = "$dapi;$env:PATH"
  }

  Add-Type -Path $dll

  $options = [Bloomberglp.Blpapi.SessionOptions]::new()
  $options.ServerHost = $BlpHost
  $options.ServerPort = $BlpPort
  $session = [Bloomberglp.Blpapi.Session]::new($options)

  if (-not $session.Start()) {
    throw "Bloomberg session failed to start. Check Bloomberg Terminal login."
  }

  try {
    if (-not $session.OpenService("//blp/refdata")) {
      throw "Bloomberg //blp/refdata service failed to open."
    }

    $service = $session.GetService("//blp/refdata")
    $request = $service.CreateRequest("ReferenceDataRequest")
    foreach ($security in $allSecurities) {
      $request.GetElement("securities").AppendValue($security)
    }
    foreach ($field in $fields.Keys) {
      $request.GetElement("fields").AppendValue($field)
    }

    $null = $session.SendRequest($request, $null)
    $output = @{}
    $errors = @{}

    while ($true) {
      $event = $session.NextEvent(10000)
      foreach ($message in $event.GetMessages()) {
        if ($message.HasElement("responseError")) {
          throw $message.GetElement("responseError").ToString()
        }
        if (-not $message.HasElement("securityData")) {
          continue
        }
        $securityData = $message.GetElement("securityData")
        for ($i = 0; $i -lt $securityData.NumValues; $i++) {
          $item = $securityData.GetValueAsElement($i)
          $security = [string]$item.GetElementAsString("security")
          if ($item.HasElement("securityError")) {
            $errors[$security] = $item.GetElement("securityError").ToString()
            continue
          }
          $fieldData = $item.GetElement("fieldData")
          $row = @{}
          foreach ($source in $fields.Keys) {
            $target = $fields[$source]
            if ($fieldData.HasElement($source) -and -not $fieldData.GetElement($source).IsNull) {
              $value = $fieldData.GetElement($source).GetValue()
              if ($source -eq "CHG_PCT_1D") {
                $value = [double]$value / 100.0
              }
              $row[$target] = $value
            } else {
              $row[$target] = $null
            }
          }
          if ($null -eq $row["avgTurnover3m"] -and $null -ne $row["avgVolume3m"] -and $null -ne $row["price"]) {
            $row["avgTurnover3m"] = [double]$row["avgVolume3m"] * [double]$row["price"]
          }
          $row.Remove("avgVolume3m")
          if ($null -eq $row["prevClose"] -and $null -ne $row["price"] -and $null -ne $row["change"] -and [double]$row["change"] -ne -1) {
            $row["prevClose"] = [double]$row["price"] / (1.0 + [double]$row["change"])
          }
          $output[$security] = $row
        }
      }
      if ($event.ToString() -match "ResponseEvent|AdhocResponseEvent|RESPONSE") {
        break
      }
    }

    $fxRow = $output["USDKRW Curncy"]
    $fx = if ($fxRow -and $fxRow["price"]) { [double]$fxRow["price"] } else { 1.0 }
    $output.Remove("USDKRW Curncy")
    Write-JsonAndExit ([ordered]@{
      securities = $output
      fx = $fx
      errors = $errors
      asOf = (Get-Date).ToString("yyyy-MM-dd HH:mm")
    }) 0
  } finally {
    $session.Stop()
  }
} catch {
  Write-JsonAndExit ([ordered]@{ error = $_.Exception.Message }) 1
}
