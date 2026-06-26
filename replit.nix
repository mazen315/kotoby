{ pkgs }: {
  deps = [
    pkgs.python39Full
    pkgs.gunicorn
  ];

  shellHook = ''
    python -m pip install --upgrade pip setuptools wheel
    if [ -f requirements.txt ]; then
      pip install -r requirements.txt
    fi
  '';
}
