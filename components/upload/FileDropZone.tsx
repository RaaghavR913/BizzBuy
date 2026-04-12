'use client';

import React, { useCallback, useState } from 'react';
import { Upload, X, FileText, Image, FileSpreadsheet, AlertCircle, Loader2, Check, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ClassificationStatus } from '@/lib/types';

const ACCEPTED_FILE_TYPES = [
  'application/pdf',
  'image/png',
  'image/jpeg',
  'image/jpg',
  'image/webp',
  'text/csv',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
];

const ACCEPTED_FILE_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg', '.webp', '.csv', '.xlsx', '.xls'];

export interface FileItem {
  file: File;
  id: string;
  classificationStatus: ClassificationStatus;
  documentType?: string;
  preview?: string;
}

interface FileDropZoneProps {
  files: FileItem[];
  onFilesChange: (files: FileItem[]) => void;
  maxFiles?: number;
  maxSizeMB?: number;
  disabled?: boolean;
}

function getFileIcon(file: File) {
  if (file.type === 'application/pdf') return <FileText className="w-5 h-5 text-red-400" />;
  // eslint-disable-next-line jsx-a11y/alt-text
  if (file.type.startsWith('image/')) return <Image className="w-5 h-5 text-blue-400" aria-hidden="true" />;
  if (file.type.includes('csv') || file.name.endsWith('.csv')) return <FileSpreadsheet className="w-5 h-5 text-green-400" />;
  if (file.type.includes('spreadsheet') || file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))
    return <FileSpreadsheet className="w-5 h-5 text-green-400" />;
  return <FileText className="w-5 h-5 text-t-muted" />;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function StatusIndicator({ status }: { status: ClassificationStatus }) {
  switch (status) {
    case 'queued':
      return <span className="text-xs text-t-muted">Queued</span>;
    case 'uploading':
      return (
        <span className="flex items-center gap-1.5 text-xs text-blue-400">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Uploading
        </span>
      );
    case 'classifying':
      return (
        <span className="flex items-center gap-1.5 text-xs text-accent">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Classifying
        </span>
      );
    case 'classified':
      return (
        <span className="flex items-center gap-1.5 text-xs text-emerald-400">
          <Check className="w-3.5 h-3.5" />
          Classified
        </span>
      );
    case 'error':
      return (
        <span className="flex items-center gap-1.5 text-xs text-risk-critical">
          <AlertTriangle className="w-3.5 h-3.5" />
          Error
        </span>
      );
  }
}

export function FileDropZone({
  files,
  onFilesChange,
  maxFiles = 10,
  maxSizeMB = 20,
  disabled = false,
}: FileDropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addFiles = useCallback(
    (newFiles: File[]) => {
      setError(null);
      const valid: FileItem[] = [];

      for (const file of newFiles) {
        if (files.length + valid.length >= maxFiles) {
          setError(`Maximum ${maxFiles} files allowed.`);
          break;
        }
        if (file.size > maxSizeMB * 1024 * 1024) {
          setError(`${file.name} exceeds the ${maxSizeMB}MB size limit.`);
          continue;
        }
        const lowerName = file.name.toLowerCase();
        const isAccepted =
          ACCEPTED_FILE_TYPES.includes(file.type) ||
          ACCEPTED_FILE_EXTENSIONS.some((extension) => lowerName.endsWith(extension));
        if (!isAccepted) {
          setError(`${file.name} is not a supported format. Use PDF, PNG, JPG, JPEG, WebP, CSV, XLSX, or XLS.`);
          continue;
        }
        valid.push({
          file,
          id: `${file.name}-${Date.now()}-${Math.random()}`,
          classificationStatus: 'queued',
        });
      }
      if (valid.length > 0) onFilesChange([...files, ...valid]);
    },
    [files, maxFiles, maxSizeMB, onFilesChange]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      if (!disabled) addFiles(Array.from(e.dataTransfer.files));
    },
    [addFiles, disabled]
  );

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && !disabled) addFiles(Array.from(e.target.files));
      e.target.value = '';
    },
    [addFiles, disabled]
  );

  const removeFile = useCallback(
    (id: string) => onFilesChange(files.filter((f) => f.id !== id)),
    [files, onFilesChange]
  );

  return (
    <div className="space-y-4">
      <div
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        className={cn(
          'relative border-2 border-dashed rounded-2xl p-10 text-center transition-all duration-200',
          disabled
            ? 'border-white/[0.05] bg-surface/50 cursor-not-allowed opacity-60'
            : isDragOver
              ? 'border-accent bg-accent/5 shadow-lg shadow-accent/10 cursor-pointer'
              : 'border-white/[0.1] bg-surface hover:border-accent/30 hover:bg-surface cursor-pointer'
        )}
        onClick={() => { if (!disabled) document.getElementById('file-input')?.click(); }}
      >
        <input
          id="file-input"
          type="file"
          multiple
          accept={ACCEPTED_FILE_EXTENSIONS.join(',')}
          className="hidden"
          onChange={onInputChange}
          disabled={disabled}
        />
        <Upload className={cn('w-10 h-10 mx-auto mb-3 transition-colors', isDragOver ? 'text-accent' : 'text-t-muted')} />
        <p className="text-base font-semibold text-white mb-1">
          {isDragOver ? 'Drop files here' : 'Drag & drop your documents'}
        </p>
        <p className="text-sm text-t-secondary mb-4">or click to browse — AI will classify each file automatically</p>
        <div className="flex items-center justify-center gap-2">
          {['PDF', 'PNG', 'JPG', 'WebP', 'CSV', 'XLSX', 'XLS'].map((fmt) => (
            <span
              key={fmt}
              className="px-2.5 py-1 bg-raised text-t-secondary rounded text-xs font-medium border border-white/[0.06]"
            >
              {fmt}
            </span>
          ))}
        </div>
        <p className="text-xs text-t-muted mt-3">Max {maxFiles} files · {maxSizeMB}MB per file</p>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-risk-critical text-sm bg-risk-critical/10 border border-risk-critical/20 rounded-lg px-4 py-3">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {files.length > 0 && (
        <div className="space-y-3">
          {files.map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-3 p-4 bg-surface border border-white/[0.06] rounded-xl"
            >
              <div className="flex-shrink-0">{getFileIcon(item.file)}</div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">{item.file.name}</p>
                <p className="text-xs text-t-muted">{formatFileSize(item.file.size)}</p>
              </div>
              <div className="flex-shrink-0">
                <StatusIndicator status={item.classificationStatus} />
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); removeFile(item.id); }}
                disabled={disabled}
                className="flex-shrink-0 p-1.5 text-t-muted hover:text-risk-critical hover:bg-risk-critical/10 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
