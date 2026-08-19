{{/*
Chart name (also the resource base name). The name is kept stable as
"fairgame" so the service name matches the ingress backend referenced in
values.yaml regardless of the Helm release name.
*/}}
{{- define "fairgame.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "fairgame.fullname" -}}
{{- default (include "fairgame.name" .) .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Common metadata labels. */}}
{{- define "fairgame.labels" -}}
app.kubernetes.io/name: {{ include "fairgame.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
{{- end -}}

{{/* Labels used for pod selection (must be stable across upgrades). */}}
{{- define "fairgame.selectorLabels" -}}
app.kubernetes.io/name: {{ include "fairgame.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
