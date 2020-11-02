{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "simbad2k.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "simbad2k.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "simbad2k.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Astropy Cache Directory
*/}}
{{- define "simbad2k.astropyCacheDirectory" -}}
{{- printf "/tmp/astropy-cache" -}}
{{- end -}}

{{/*
Astropy Config Directory
*/}}
{{- define "simbad2k.astropyConfigDirectory" -}}
{{- printf "/tmp/astropy-config" -}}
{{- end -}}

{{/*
Create the environment variables for configuration of this project. They are
repeated in a bunch of places, so to keep from repeating ourselves, we'll
build it here and use it everywhere.
*/}}
{{- define "simbad2k.backendEnv" -}}
- name: XDG_CACHE_HOME
  value: {{ include "simbad2k.astropyCacheDirectory" . | quote }}
- name: XDG_CONFIG_HOME
  value: {{ include "simbad2k.astropyConfigDirectory" . | quote }}
{{- end -}}
