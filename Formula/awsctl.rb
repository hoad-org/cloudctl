class Awsctl < Formula
  include Language::Python::Virtualenv

  desc "Enterprise Cloud Identity & Context Manager (AWS, Azure, GCP)"
  homepage "https://github.com/beyondtrust-cloudops/aws-terraform-infra-cloudops-awsctl"
  # Update url and sha256 before releasing a tagged version.
  # To compute sha256: curl -L <url> | shasum -a 256
  url "https://github.com/beyondtrust-cloudops/aws-terraform-infra-cloudops-awsctl/archive/refs/tags/v3.0.0.tar.gz"
  sha256 "REPLACE_WITH_ACTUAL_SHA256"
  license "MIT"
  head "https://github.com/beyondtrust-cloudops/aws-terraform-infra-cloudops-awsctl.git", branch: "main"

  depends_on "python@3.12"

  # Core runtime dependencies (mirrors pyproject.toml)
  resource "boto3" do
    url "https://files.pythonhosted.org/packages/source/b/boto3/boto3-1.34.0.tar.gz"
    sha256 "REPLACE_boto3"
  end

  resource "pyyaml" do
    url "https://files.pythonhosted.org/packages/source/P/PyYAML/PyYAML-6.0.1.tar.gz"
    sha256 "bfdf460b1736c775f2ba9f6a92bca30bc2095067b8a9d77876d1fad6cc3b4a43"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-13.7.0.tar.gz"
    sha256 "REPLACE_rich"
  end

  resource "inquirerpy" do
    url "https://files.pythonhosted.org/packages/source/I/InquirerPy/InquirerPy-0.3.4.tar.gz"
    sha256 "REPLACE_inquirerpy"
  end

  def install
    # Build a self-contained virtualenv in libexec so the formula is hermetic
    # and does not pollute the user's system Python.
    venv = virtualenv_create(libexec/"venv", "python3.12")
    venv.pip_install resources
    venv.pip_install buildpath

    # Shim scripts: forward all args to the virtualenv binaries so `awsctl`
    # resolves to the correct interpreter regardless of PATH order.
    (bin/"awsctl").write_env_script(libexec/"venv/bin/awsctl",
      PATH: "#{libexec}/venv/bin:$PATH")
    (bin/"_awsctl_bin").write_env_script(libexec/"venv/bin/_awsctl_bin",
      PATH: "#{libexec}/venv/bin:$PATH")
  end

  def post_install
    # Install the shell wrapper into the user's detected shell profile.
    # awsctl init --shell-only is non-interactive and safe to run in post_install.
    system bin/"awsctl", "init", "--shell-only"
  rescue => e
    opoo "Shell integration could not be installed automatically: #{e}\n" \
         "Run `awsctl init --shell-only` manually after reloading your shell."
  end

  def caveats
    <<~EOS
      awsctl has been installed.

      To enable the shell wrapper (required for `awsctl switch` to set env vars):
        awsctl init --shell-only

      Then reload your shell:
        source ~/.zshrc    # or ~/.bashrc / ~/.bash_profile

      To configure your first organization:
        awsctl org add

      Or run the full wizard:
        awsctl init
    EOS
  end

  test do
    system bin/"awsctl", "--version"
  end
end
