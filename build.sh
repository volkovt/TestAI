#!/usr/bin/env bash
set -e

# Ajusta para o diretório onde o script está
cd "$(dirname "$0")"

echo "==============================================="
echo " TestAI Build Script"
echo "==============================================="
echo "1) Gerar Onedir (pasta + _internal)"
echo "2) Gerar Onefile (unico EXE)"
echo "3) Gerar Ambos"
echo
read -p "Escolha uma opcao [1-3]: " escolha

case "$escolha" in
  1)
    echo
    echo "[1] Gerando Onedir..."
    pyinstaller --clean --noconfirm TestAI_onedir.spec
    ;;
  2)
    echo
    echo "[2] Gerando Onefile..."
    pyinstaller --clean --noconfirm TestAI.spec
    ;;
  3)
    echo
    echo "[1] Gerando Onedir..."
    pyinstaller --clean --noconfirm TestAI_onedir.spec

    echo
    echo "[2] Gerando Onefile..."
    pyinstaller --clean --noconfirm TestAI.spec
    ;;
  *)
    echo "Opcao invalida. Saindo..."
    exit 1
    ;;
esac

echo
echo "Build(s) concluido(s)."
