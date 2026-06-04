"use client";

import { FormEvent, useMemo, useState } from "react";

import { Modal } from "@/components/ui";
import { ApiError, api } from "@/lib/api";

interface ContactFormState {
  name: string;
  email: string;
  subject: string;
  message: string;
  company: string;
}

type ContactField = keyof ContactFormState;

const INITIAL_FORM: ContactFormState = {
  name: "",
  email: "",
  subject: "",
  message: "",
  company: "",
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SUCCESS_MESSAGE = "문의가 정상적으로 접수되었습니다.";

function normalizeEmail(value: string) {
  return value.trim().toLowerCase();
}

function validateForm(form: ContactFormState): Partial<Record<ContactField, string>> {
  const errors: Partial<Record<ContactField, string>> = {};
  const name = form.name.trim();
  const email = normalizeEmail(form.email);
  const subject = form.subject.trim();
  const message = form.message.trim();

  if (name.length < 1) errors.name = "이름을 입력해 주세요.";
  else if (name.length > 80) errors.name = "이름은 최대 80자까지 입력할 수 있습니다.";

  if (!EMAIL_PATTERN.test(email)) errors.email = "이메일 형식을 올바르게 입력해 주세요.";
  else if (email.length > 120) errors.email = "이메일은 최대 120자까지 입력할 수 있습니다.";

  if (subject.length < 1) errors.subject = "제목을 입력해 주세요.";
  else if (subject.length > 120) errors.subject = "제목은 최대 120자까지 입력할 수 있습니다.";

  if (message.length < 10) errors.message = "메시지는 최소 10자 이상 입력해야 합니다.";
  else if (message.length > 3000) errors.message = "메시지는 최대 3000자까지 입력할 수 있습니다.";

  return errors;
}

function errorToMessage(error: unknown) {
  if (error instanceof ApiError) {
    return error.detail || error.message || "문의 접수 중 오류가 발생했습니다.";
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "문의 접수 중 오류가 발생했습니다.";
}

export default function ContactSection() {
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<ContactFormState>(INITIAL_FORM);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<ContactField, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const [statusMessage, setStatusMessage] = useState("");

  const statusTone = useMemo(() => {
    if (status === "success") return "text-positive";
    if (status === "error") return "text-negative";
    return "text-text-secondary";
  }, [status]);

  const updateField = (field: ContactField, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setFieldErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
    if (status !== "idle") {
      setStatus("idle");
      setStatusMessage("");
    }
  };

  const closeModal = () => {
    if (submitting) return;
    setModalOpen(false);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors = validateForm(form);
    setFieldErrors(nextErrors);

    if (Object.keys(nextErrors).length > 0) {
      setStatus("error");
      setStatusMessage(Object.values(nextErrors)[0] || "입력값을 확인해 주세요.");
      return;
    }

    setSubmitting(true);
    setStatus("idle");
    setStatusMessage("");

    try {
      const response = await api.submitContact({
        name: form.name.trim(),
        email: normalizeEmail(form.email),
        subject: form.subject.trim(),
        message: form.message.trim(),
        company: form.company,
      });
      setForm(INITIAL_FORM);
      setFieldErrors({});
      setStatus("success");
      setStatusMessage(response.message || SUCCESS_MESSAGE);
    } catch (error) {
      setStatus("error");
      setStatusMessage(errorToMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <footer className="border-t border-border/70 py-8 sm:py-10" aria-labelledby="contact-title">
      <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0 space-y-3">
          <div>
            <h2 id="contact-title" className="text-xl font-bold text-text">
              Yoongeon Choi
            </h2>
            <p className="mt-2 text-sm leading-6 text-text-secondary">
              Data Engineering · AI Infrastructure · Web Projects
            </p>
          </div>
          <a
            className="inline-flex min-h-[var(--touch-target-min)] max-w-full items-center break-all font-mono text-sm font-semibold text-accent transition-colors hover:text-accent-strong"
            href="mailto:contact@yoongeon.xyz"
          >
            contact@yoongeon.xyz
          </a>
          <nav className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm font-semibold text-text-secondary" aria-label="Contact links">
            <a
              className="transition-colors hover:text-text"
              href="https://github.com/YoongeonChoi"
              rel="noreferrer"
              target="_blank"
            >
              GitHub
            </a>
            <span aria-hidden="true">·</span>
            <a
              className="transition-colors hover:text-text"
              href="https://www.linkedin.com/in/yoongeon-choi-83b434339"
              rel="noreferrer"
              target="_blank"
            >
              LinkedIn
            </a>
            <span aria-hidden="true">·</span>
            <span>Privacy</span>
          </nav>
          <p className="text-xs text-text-secondary">
            © 2026 Yoongeon Choi. All rights reserved.
          </p>
        </div>
        <button className="ui-button-primary w-full px-5 sm:w-auto" type="button" onClick={() => setModalOpen(true)}>
          문의 보내기
        </button>
      </div>

      <Modal className="max-h-[calc(100vh-2rem)] overflow-y-auto sm:max-w-2xl" onClose={closeModal} open={modalOpen} title="문의 보내기">
        <p className="mb-5 text-sm leading-6 text-text-secondary">
          프로젝트, 채용, 협업 문의를 남겨 주세요. 접수된 내용은 contact@yoongeon.xyz로 확인합니다.
        </p>
        <form className="min-w-0 space-y-4" onSubmit={handleSubmit} noValidate>
          <div className="hidden" aria-hidden="true">
            <label htmlFor="contact-company">회사</label>
            <input
              id="contact-company"
              name="company"
              tabIndex={-1}
              autoComplete="off"
              value={form.company}
              onChange={(event) => updateField("company", event.target.value)}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="ui-field-label" htmlFor="contact-name">
                이름
              </label>
              <input
                id="contact-name"
                name="name"
                className="ui-input"
                value={form.name}
                onChange={(event) => updateField("name", event.target.value)}
                autoComplete="name"
                maxLength={80}
                aria-invalid={Boolean(fieldErrors.name)}
                aria-describedby={fieldErrors.name ? "contact-name-error" : undefined}
              />
              {fieldErrors.name ? (
                <p id="contact-name-error" className="ui-helper-text text-negative">
                  {fieldErrors.name}
                </p>
              ) : null}
            </div>

            <div>
              <label className="ui-field-label" htmlFor="contact-email">
                이메일
              </label>
              <input
                id="contact-email"
                name="email"
                type="email"
                className="ui-input"
                value={form.email}
                onChange={(event) => updateField("email", event.target.value)}
                autoComplete="email"
                maxLength={120}
                aria-invalid={Boolean(fieldErrors.email)}
                aria-describedby={fieldErrors.email ? "contact-email-error" : undefined}
              />
              {fieldErrors.email ? (
                <p id="contact-email-error" className="ui-helper-text text-negative">
                  {fieldErrors.email}
                </p>
              ) : null}
            </div>
          </div>

          <div>
            <label className="ui-field-label" htmlFor="contact-subject">
              제목
            </label>
            <input
              id="contact-subject"
              name="subject"
              className="ui-input"
              value={form.subject}
              onChange={(event) => updateField("subject", event.target.value)}
              maxLength={120}
              aria-invalid={Boolean(fieldErrors.subject)}
              aria-describedby={fieldErrors.subject ? "contact-subject-error" : undefined}
            />
            {fieldErrors.subject ? (
              <p id="contact-subject-error" className="ui-helper-text text-negative">
                {fieldErrors.subject}
              </p>
            ) : null}
          </div>

          <div>
            <label className="ui-field-label" htmlFor="contact-message">
              메시지
            </label>
            <textarea
              id="contact-message"
              name="message"
              className="ui-textarea min-h-[11rem] resize-y"
              value={form.message}
              onChange={(event) => updateField("message", event.target.value)}
              maxLength={3000}
              aria-invalid={Boolean(fieldErrors.message)}
              aria-describedby={fieldErrors.message ? "contact-message-error" : undefined}
            />
            {fieldErrors.message ? (
              <p id="contact-message-error" className="ui-helper-text text-negative">
                {fieldErrors.message}
              </p>
            ) : null}
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className={`min-h-[1.5rem] text-sm leading-6 ${statusTone}`} aria-live="polite">
              {statusMessage}
            </p>
            <button className="ui-button-primary shrink-0" type="submit" disabled={submitting}>
              {submitting ? "보내는 중" : "보내기"}
            </button>
          </div>
        </form>
      </Modal>
    </footer>
  );
}
