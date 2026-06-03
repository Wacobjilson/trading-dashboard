{{/* Common name + label helpers */}}

{{- define "quanta.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "quanta.fullname" -}}
{{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "quanta.labels" -}}
app.kubernetes.io/name: {{ include "quanta.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{/* Name of the secret to use (existing or chart-created) */}}
{{- define "quanta.secretName" -}}
{{- if .Values.secret.existingSecret -}}
{{ .Values.secret.existingSecret }}
{{- else -}}
{{ include "quanta.fullname" . }}-secrets
{{- end -}}
{{- end -}}

{{/* Postgres connection URL built from values + secret password */}}
{{- define "quanta.databaseUrl" -}}
postgres://{{ .Values.postgres.user }}:$(POSTGRES_PASSWORD)@{{ include "quanta.fullname" . }}-postgres:5432/{{ .Values.postgres.database }}?sslmode=disable
{{- end -}}

{{- define "quanta.image" -}}
{{- printf "%s/%s-%s:%s" .Values.image.registry .Values.image.repository .component .tag -}}
{{- end -}}
